from fastapi import HTTPException
from sqlalchemy import and_, exists, or_, select, update
from sqlalchemy.orm import aliased

from app.models import Occurrence, Trip, TripInvoice
from app.models.entities import utcnow
from app.models.enums import DeliveryStatus, OccurrenceType, TripStatus
from app.services.audit import audit

REASONS = {
    "CLIENTE_FECHADO": "Cliente fechado",
    "CLIENTE_RECUSOU": "Cliente não quis receber",
    "CLIENTE_AUSENTE": "Destinatário ausente",
    "ENDERECO_NAO_LOCALIZADO": "Endereço não localizado",
    "MERCADORIA_RECUSADA": "Mercadoria recusada",
    "OUTRO": "Outro",
}
UNRESOLVED = (DeliveryStatus.PENDENTE, DeliveryStatus.EM_ENTREGA)


def transition(db, trip, invoice_id, user, action, payload=None):
    invoice = next((n for n in trip.invoices if n.id == invoice_id), None)
    if not invoice:
        raise HTTPException(404, "Entrega não encontrada nesta rota")
    if trip.status != TripStatus.EM_ANDAMENTO:
        raise HTTPException(409, "A rota precisa estar em andamento")
    previous = DeliveryStatus.PENDENTE if action == "start" else DeliveryStatus.EM_ENTREGA
    target = {"start": DeliveryStatus.EM_ENTREGA, "finish": DeliveryStatus.ENTREGUE, "occurrence": DeliveryStatus.NAO_ENTREGUE}[action]
    if invoice.status != previous:
        raise HTTPException(409, "Esta entrega não permite esta ação; atualize a rota")
    claim_revision(db, trip, trip.delivery_revision)
    now = utcnow()
    values = {"status": target}
    values[{"start": "started_at", "finish": "delivered_at", "occurrence": "occurrence_at"}[action]] = (invoice.started_at or now) if action == "start" else now
    if payload:
        values.update(occurrence_reason=payload.motivo, occurrence_note=payload.observacao)
    earlier = aliased(TripInvoice)
    # Conditional update protects against retries/concurrent requests, including SQLite.
    result = db.execute(update(TripInvoice).where(
        TripInvoice.id == invoice_id,
        TripInvoice.trip_id == trip.id,
        TripInvoice.status == previous,
        ~exists(select(earlier.id).where(earlier.trip_id == trip.id, or_(earlier.position < invoice.position, and_(earlier.position == invoice.position, earlier.id < invoice_id)), earlier.status.in_(UNRESOLVED))),
        exists(select(Trip.id).where(Trip.id == trip.id, Trip.status == TripStatus.EM_ANDAMENTO)),
    ).values(**values).execution_options(synchronize_session=False))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Resolva a entrega atual antes de continuar ou atualize a rota")
    if payload:
        occurrence = Occurrence(invoice_id=invoice_id, trip_id=trip.id, driver_id=trip.driver_id,
            vehicle_id=trip.vehicle_id,
            tipo=OccurrenceType.CLIENTE_AUSENTE if payload.motivo == "CLIENTE_AUSENTE" else OccurrenceType.PROBLEMA_ENTREGA,
            descricao=f"NF {invoice.numero_nota}: {REASONS[payload.motivo]}" + (f" · {payload.observacao}" if payload.observacao else ""),
            data_hora=now)
        db.add(occurrence)
    audit(db, user, {"start": "INICIAR_ENTREGA", "finish": "FINALIZAR_ENTREGA", "occurrence": "REGISTRAR_OCORRENCIA_ENTREGA"}[action],
        "TRIP_INVOICE", invoice_id, {"trip_id": trip.id, "driver_id": trip.driver_id,
        "numero_nota": invoice.numero_nota, "status_anterior": previous.value, "status_novo": target.value,
        "quando": now.isoformat()})
    db.commit()
    db.refresh(invoice)
    return invoice


def claim_revision(db, trip, revision):
    # Shared compare-and-swap also serializes order changes on SQLite.
    result = db.execute(update(Trip).where(Trip.id == trip.id, Trip.delivery_revision == revision, Trip.status == trip.status).values(
        delivery_revision=revision + 1
    ).execution_options(synchronize_session="fetch"))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "A rota mudou. Atualize antes de tentar novamente.")


def reorder(db, trip, payload, user):
    if trip.status not in (TripStatus.ABERTA, TripStatus.EM_ANDAMENTO):
        raise HTTPException(409, "Esta rota j\u00e1 foi encerrada")
    old = [n.id for n in trip.invoices]
    new = payload.invoice_ids
    if len(new) != len(set(new)) or set(new) != set(old):
        raise HTTPException(422, "Informe todas as notas desta rota uma vez, sem adicionar ou remover entregas")
    by_id = {n.id: n for n in trip.invoices}
    for index, invoice in enumerate(trip.invoices):
        if invoice.status not in UNRESOLVED and new[index] != invoice.id:
            raise HTTPException(409, "Entregas j\u00e1 tratadas mant\u00eam sua posi\u00e7\u00e3o no hist\u00f3rico")
    if payload.revision != trip.delivery_revision:
        raise HTTPException(409, "A rota mudou. Atualize antes de tentar novamente.")
    if old == new:
        return
    claim_revision(db, trip, payload.revision)
    first = next((id for id in new if by_id[id].status in UNRESOLVED), None)
    postponed = []
    for index, id in enumerate(new, start=1):
        invoice = by_id[id]
        invoice.position = index
        if invoice.status == DeliveryStatus.EM_ENTREGA and id != first:
            invoice.status = DeliveryStatus.PENDENTE
            postponed.append(id)
            audit(db, user, "ADIAR_ENTREGA", "TRIP_INVOICE", id, {
                "trip_id": trip.id, "driver_id": trip.driver_id,
                "status_anterior": "EM_ENTREGA", "status_novo": "PENDENTE",
                "started_at": invoice.started_at.isoformat() if invoice.started_at else None,
                "quando": utcnow().isoformat(),
            })
    audit(db, user, "REORDENAR_ENTREGAS", "TRIP", trip.id, {
        "driver_id": trip.driver_id, "ordem_anterior": old, "ordem_nova": new,
        "entregas_adiadas": postponed, "quando": utcnow().isoformat(),
    })
    db.commit()
