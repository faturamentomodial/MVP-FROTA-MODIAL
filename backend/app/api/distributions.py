"""Atomic distribution editing, preserving the existing operational RoutePlan."""
from copy import deepcopy
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.api.dependencies import require_admin
from app.core.database import get_db
from app.models import Trip
from app.models.enums import TripStatus
from app.models.route_plans import Distribution, DistributionVersion, DistributionRoute, RoutePlan, RoutePlanVersion
from app.schemas.distributions import DistributionInput
from app.schemas.route_plans import invoice_identity
from app.api.route_plans import output, validate_vehicle

router = APIRouter(prefix='/distributions', tags=['Central de distribuição'], dependencies=[Depends(require_admin)])


def load(db, distribution_id):
    item = db.get(Distribution, distribution_id)
    if not item:
        raise HTTPException(404, 'Distribuição não encontrada')
    return item


def detail_output(db, item):
    result = {'id': item.id, 'name': item.name, 'revision': item.revision, **deepcopy(item.data)}
    active = list(db.scalars(select(Trip).where(Trip.status.in_([TripStatus.ABERTA, TripStatus.EM_ANDAMENTO]))))
    for route in result['routes']:
        plan = db.get(RoutePlan, route['plan_id'])
        route['plan'] = output(plan)
        notes = {invoice_identity(n): n['id'] for n in result['notes'] if n['id'] in route['invoice_ids']}
        route['invoice_ids'] = [notes[invoice_identity(n)] for n in plan.data['invoices']]
        trip_id = plan.data.get('trip_id')
        trip = db.get(Trip, trip_id) if trip_id else None
        route['delivery_statuses'] = {n.numero_nota: n.status.value for n in trip.invoices} if trip else {}
        route['resource_warnings'] = [f'Viagem #{t.id} aberta com o mesmo motorista ou veículo. A disponibilidade será validada novamente ao iniciar a saída.' for t in active if t.id != trip_id and (t.driver_id == plan.data.get('driver_id') or t.vehicle_id == plan.data.get('vehicle_id'))]
    return result


@router.get('')
def list_distributions(db: Session = Depends(get_db), limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0)):
    return [{'id': d.id, 'name': d.name, 'revision': d.revision} for d in db.scalars(select(Distribution).order_by(Distribution.id.desc()).offset(offset).limit(limit))]


@router.post('', status_code=201)
def create(payload: DistributionInput, db: Session = Depends(get_db), user=Depends(require_admin)):
    if payload.notes or payload.routes or payload.revision:
        raise HTTPException(422, 'Crie um conjunto vazio antes de adicionar notas e rotas')
    item = Distribution(name=payload.name, data={'notes': [], 'routes': []}, created_by=user.id)
    db.add(item)
    db.flush()
    db.add(DistributionVersion(distribution_id=item.id, revision=0, data={'name': item.name, **item.data}, created_by=user.id))
    db.commit()
    return detail_output(db, item)


@router.get('/{distribution_id}')
def detail(distribution_id: int, db: Session = Depends(get_db)):
    return detail_output(db, load(db, distribution_id))


@router.get('/{distribution_id}/versions')
def versions(distribution_id: int, db: Session = Depends(get_db)):
    load(db, distribution_id)
    return [{'revision': v.revision, 'data': v.data} for v in db.scalars(select(DistributionVersion).where(DistributionVersion.distribution_id == distribution_id).order_by(DistributionVersion.revision))]


@router.put('/{distribution_id}')
def edit(distribution_id: int, payload: DistributionInput, db: Session = Depends(get_db), user=Depends(require_admin)):
    item = load(db, distribution_id)
    previous = deepcopy(item.data)
    claimed = db.execute(update(Distribution).where(Distribution.id == item.id, Distribution.revision == payload.revision).values(revision=payload.revision + 1), execution_options={'synchronize_session': False})
    if claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'Distribuição alterada por outro usuário. Recarregue antes de editar.')
    try:
        old_routes = {r['key']: r for r in previous['routes']}
        new_keys = {r.key for r in payload.routes}
        if not set(old_routes).issubset(new_keys):
            raise HTTPException(422, 'Rotas salvas devem ser preservadas; remova ou transfira suas notas em rascunho')
        notes = {n.id: n.model_dump() for n in payload.notes}
        routes = []
        for incoming in payload.routes:
            old = old_routes.get(incoming.key)
            if (old and incoming.plan_id != old['plan_id']) or (not old and incoming.plan_id is not None):
                raise HTTPException(409, 'Vínculo de planejamento inválido')
            data = incoming.plan.model_dump(exclude={'revision', 'invoices'})
            data['invoices'] = [{k: notes[i][k] for k in ('number', 'volumes', 'destination', 'source', 'external_id', 'company', 'series', 'partner')} for i in incoming.invoice_ids]
            # Existing operational cargo is keyed by visible number. Keep this
            # contract: same-number documents can coexist in the pool, not a trip.
            if len({n['number'] for n in data['invoices']}) != len(data['invoices']):
                raise HTTPException(422, 'NFs com mesmo número devem ser distribuídas em rotas diferentes para preservar a identificação operacional')
            validate_vehicle(db, incoming.plan)
            if old:
                plan = db.get(RoutePlan, old['plan_id'])
                if plan.revision != incoming.plan.revision:
                    raise HTTPException(409, 'Rota alterada por outro usuário. Recarregue a distribuição.')
                comparable = {k: plan.data.get(k) for k in data}
                if plan.status != 'RASCUNHO':
                    old_notes = {n['id']: n for n in previous['notes']}
                    if comparable != data or set(old['invoice_ids']) != set(incoming.invoice_ids) or old['color'] != incoming.color or any(old_notes[i] != notes[i] for i in old['invoice_ids']):
                        raise HTTPException(409, 'Uma rota confirmada ou iniciada não pode ser alterada')
                elif comparable != data:
                    data.update(stops=[], result=None)
                    changed = db.execute(update(RoutePlan).where(RoutePlan.id == plan.id, RoutePlan.revision == incoming.plan.revision, RoutePlan.status == 'RASCUNHO').values(revision=incoming.plan.revision + 1, data=data), execution_options={'synchronize_session': False})
                    if changed.rowcount != 1:
                        raise HTTPException(409, 'Rota alterada ou confirmada durante a edição')
                    db.add(RoutePlanVersion(plan_id=plan.id, revision=incoming.plan.revision + 1, data={'status': 'RASCUNHO', **data}, created_by=user.id))
                    db.expire(plan)
                # Lock even unchanged plans against concurrent confirmation while
                # editing distribution metadata, and verify revision atomically.
                else:
                    matched = db.execute(update(RoutePlan).where(RoutePlan.id == plan.id, RoutePlan.revision == incoming.plan.revision, RoutePlan.status == 'RASCUNHO').values(revision=RoutePlan.revision), execution_options={'synchronize_session': False})
                    if matched.rowcount != 1:
                        raise HTTPException(409, 'Rota confirmada durante a edição')
                link = db.get(DistributionRoute, plan.id)
                link.color = incoming.color
            else:
                data.update(stops=[], result=None)
                plan = RoutePlan(data=data, created_by=user.id)
                db.add(plan)
                db.flush()
                db.add(RoutePlanVersion(plan_id=plan.id, revision=0, data={'status': 'RASCUNHO', **data}, created_by=user.id))
                db.add(DistributionRoute(plan_id=plan.id, distribution_id=item.id, key=incoming.key, color=incoming.color))
            routes.append({'key': incoming.key, 'plan_id': plan.id, 'color': incoming.color, 'invoice_ids': incoming.invoice_ids})
        item.name = payload.name
        item.data = {'notes': list(notes.values()), 'routes': routes}
        db.add(DistributionVersion(distribution_id=item.id, revision=payload.revision + 1, data={'name': item.name, **deepcopy(item.data)}, created_by=user.id))
        db.commit()
        db.refresh(item)
        return detail_output(db, item)
    except Exception:
        db.rollback()
        raise
