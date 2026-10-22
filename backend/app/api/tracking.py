from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import require_admin
from app.core.database import get_db
from app.models import Trip, User, Vehicle
from app.models.entities import TrackingPositionRecord, VehicleTracking
from app.models.enums import TripStatus
from app.schemas.domain import ORMModel
from app.services.audit import audit
from app.services.tracking import provider, ProviderNotConfigured, ProviderUnavailable, sync_latest, persist_positions, sync_lock

router = APIRouter(prefix="/tracking", tags=["Rastreamento"], dependencies=[Depends(require_admin)])


class TrackingLink(BaseModel):
    provider: Literal["POSITRON"] = "POSITRON"
    tracker_id: str = Field(min_length=1, max_length=120)
    active: bool = True

    @field_validator("tracker_id")
    @classmethod
    def trim_id(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Informe o ID do rastreador")
        return value


class PositionOut(ORMModel):
    latitude: float
    longitude: float
    recorded_at: datetime
    speed: float | None
    address: str | None


def as_utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@router.get("")
def fleet(db: Session = Depends(get_db)):
    message = None
    ready = False
    if provider.configured:
        try:
            sync_latest(db)
            ready = True
        except (ProviderNotConfigured, ProviderUnavailable) as exc:
            message = str(exc)
    else:
        message = "Configure as credenciais próprias da integração Pósitron no backend."
    links = {link.vehicle_id: link for link in db.scalars(select(VehicleTracking))}
    trips = {trip.vehicle_id: trip for trip in db.scalars(select(Trip).options(joinedload(Trip.driver)).where(Trip.status.in_([TripStatus.ABERTA, TripStatus.EM_ANDAMENTO])))}
    # One latest row per vehicle, without loading the entire history.
    from sqlalchemy import func
    latest = select(TrackingPositionRecord.vehicle_id, func.max(TrackingPositionRecord.recorded_at).label("time")).group_by(TrackingPositionRecord.vehicle_id).subquery()
    positions = {p.vehicle_id: p for p in db.scalars(select(TrackingPositionRecord).join(latest, (TrackingPositionRecord.vehicle_id == latest.c.vehicle_id) & (TrackingPositionRecord.recorded_at == latest.c.time)))}
    now = datetime.now(UTC)
    items = []
    for vehicle in db.scalars(select(Vehicle).order_by(Vehicle.placa)):
        link, trip, position = links.get(vehicle.id), trips.get(vehicle.id), positions.get(vehicle.id)
        status = "SEM_VINCULO" if not link else "INATIVO" if not link.active else "AGUARDANDO_POSICAO" if not position else "SEM_COMUNICACAO" if now - as_utc(position.recorded_at) > timedelta(minutes=5) else "DESCONHECIDO" if position.speed is None else "EM_MOVIMENTO" if position.speed > 0 else "PARADO"
        items.append({"vehicle_id": vehicle.id, "placa": vehicle.placa, "modelo": f"{vehicle.marca} {vehicle.modelo}", "vehicle_active": vehicle.ativo,
                      "tracker_id": link.tracker_id if link else None, "tracking_active": link.active if link else False, "status": status,
                      "position": PositionOut.model_validate(position).model_dump() if position else None,
                      "trip_id": trip.id if trip else None, "driver_name": trip.driver.nome if trip else None,
                      "trip_started_at": as_utc(trip.data_saida) if trip else None})
    return {"items": items, "checked_at": now, "provider_ready": ready, "message": message}


@router.get("/provider/vehicles")
def provider_vehicles():
    try:
        return [{"idVehicle": v["id"], "licensePlate": v["licensePlate"]} for v in provider.vehicles()]
    except ProviderNotConfigured as exc:
        raise HTTPException(503, str(exc)) from exc
    except ProviderUnavailable as exc:
        raise HTTPException(502, str(exc)) from exc


@router.put("/{vehicle_id}/link")
def link_vehicle(vehicle_id: int, payload: TrackingLink, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    if not db.get(Vehicle, vehicle_id):
        raise HTTPException(404, "Veículo não encontrado")
    link = db.get(VehicleTracking, vehicle_id)
    changed = link is not None and link.tracker_id != payload.tracker_id
    if link is None:
        link = VehicleTracking(vehicle_id=vehicle_id)
        db.add(link)
    for key, value in payload.model_dump().items():
        setattr(link, key, value)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Rastreador já vinculado a outro veículo") from exc
    # Do not mix positions from different physical trackers after reassignment.
    if changed:
        from sqlalchemy import delete
        db.execute(delete(TrackingPositionRecord).where(TrackingPositionRecord.vehicle_id == vehicle_id))
    audit(db, user, "VINCULAR_RASTREADOR", "VEHICLE", vehicle_id)
    db.commit()
    return {"vehicle_id": vehicle_id, **payload.model_dump()}


@router.get("/{vehicle_id}/history", response_model=list[PositionOut])
def history(vehicle_id: int, hours: int = Query(24, ge=1, le=168), db: Session = Depends(get_db)):
    if not db.get(Vehicle, vehicle_id):
        raise HTTPException(404, "Veículo não encontrado")
    link = db.get(VehicleTracking, vehicle_id)
    if provider.configured and link and link.active:
        if not link.tracker_id.isdecimal():
            raise HTTPException(422, "Vincule o idVehicle numérico da API Pósitron para consultar o histórico.")
        try:
            end = datetime.now(UTC)
            with sync_lock:
                persist_positions(db, provider.history(link.tracker_id, end - timedelta(hours=hours), end), {link.tracker_id: link})
        except (ProviderNotConfigured, ProviderUnavailable) as exc:
            raise HTTPException(502, str(exc)) from exc
    return db.scalars(select(TrackingPositionRecord).where(TrackingPositionRecord.vehicle_id == vehicle_id,
        TrackingPositionRecord.recorded_at >= datetime.now(UTC) - timedelta(hours=hours)).order_by(TrackingPositionRecord.recorded_at).limit(10000)).all()
