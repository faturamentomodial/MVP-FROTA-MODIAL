from copy import deepcopy
from datetime import date, datetime, time, timedelta
from math import isfinite
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.dependencies import require_admin, require_operations
from app.core.database import get_db
from app.models import Driver, Vehicle, Pickup
from app.models.route_plans import RoutePlan, RoutePlanVersion
from app.models.route_templates import RouteTemplate, RouteExecution
from app.schemas.route_templates import TemplateInput, ExecutionInput
from app.schemas.route_plans import CalculateInput, RevisionInput
from app.services import route_planning as provider
from app.services.route_scheduling import LOCAL, today, execution_status, check_conflicts
from app.api.route_plans import WARNING

router = APIRouter(tags=['Rotas estabelecidas'], dependencies=[Depends(require_operations)])


def load(db, model, id):
    item = db.get(model, id)
    if not item or (model is RouteTemplate and item.data.get('deleted', False)):
        raise HTTPException(404, 'Rota ou programação não encontrada')
    return item


def output(item):
    return {'id': item.id, 'revision': item.revision, 'status': 'ATIVA' if item.data['active'] else 'INATIVA', **item.data}


def write_template(db, item, revision, data):
    changed = db.execute(update(RouteTemplate).where(RouteTemplate.id == item.id, RouteTemplate.revision == revision)
                         .values(data=data, revision=revision+1), execution_options={'synchronize_session': False})
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'Rota alterada. Recarregue antes de salvar')
    db.commit()
    db.refresh(item)
    return output(item)


@router.get('/route-templates')
def list_templates(db: Session = Depends(get_db), limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0)):
    return [output(item) for item in db.scalars(select(RouteTemplate).where(RouteTemplate.data['deleted'].as_boolean().is_not(True)).order_by(RouteTemplate.id.desc()).limit(limit).offset(offset))]


@router.post('/route-templates', status_code=201, dependencies=[Depends(require_admin)])
def create(payload: TemplateInput, db: Session = Depends(get_db), user=Depends(require_admin)):
    item = RouteTemplate(data={**payload.model_dump(mode='json', exclude={'revision'}), 'stops': [], 'result': None}, created_by=user.id)
    db.add(item)
    db.commit()
    return output(item)


@router.get('/route-templates/{id}')
def detail(id: int, db: Session = Depends(get_db)):
    return output(load(db, RouteTemplate, id))


@router.put('/route-templates/{id}', dependencies=[Depends(require_admin)])
def edit(id: int, payload: TemplateInput, db: Session = Depends(get_db)):
    return write_template(db, load(db, RouteTemplate, id), payload.revision,
                          {**payload.model_dump(mode='json', exclude={'revision'}), 'stops': [], 'result': None})


def remove_unstarted_execution(db, item):
    plan = load(db, RoutePlan, item.plan_id)
    if plan.data.get('trip_id'):
        return False
    # Claim the same plan row as trip creation before removing its children.
    claimed = db.execute(update(RoutePlan).where(
        RoutePlan.id == plan.id, RoutePlan.revision == plan.revision,
        RoutePlan.data['trip_id'].as_integer().is_(None)
    ).values(revision=plan.revision+1), execution_options={'synchronize_session': False})
    if claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'Programacao alterada ou iniciada. Recarregue')
    db.execute(delete(RoutePlanVersion).where(RoutePlanVersion.plan_id == plan.id))
    db.execute(delete(RouteExecution).where(RouteExecution.id == item.id))
    db.execute(delete(RoutePlan).where(RoutePlan.id == plan.id))
    return True


@router.delete('/route-templates/{id}', status_code=204, dependencies=[Depends(require_admin)])
def delete_template(id: int, revision: int = Query(..., ge=0), db: Session = Depends(get_db)):
    item = load(db, RouteTemplate, id)
    claimed = db.execute(update(RouteTemplate).where(
        RouteTemplate.id == id, RouteTemplate.revision == revision
    ).values(data={**item.data, 'active': False, 'deleted': True}, revision=revision+1),
        execution_options={'synchronize_session': False})
    if claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'Rota alterada. Recarregue antes de excluir')
    db.execute(update(Pickup).where(Pickup.route_template_id == id).values(route_template_id=None))
    for execution in list(db.scalars(select(RouteExecution).where(RouteExecution.template_id == id))):
        remove_unstarted_execution(db, execution)
    # Started trips still reference their template; retain only that required parent.
    if db.scalar(select(RouteExecution.id).where(RouteExecution.template_id == id).limit(1)) is None:
        db.execute(delete(RouteTemplate).where(RouteTemplate.id == id))
    db.commit()
    return Response(status_code=204)


@router.post('/route-templates/{id}/duplicate', status_code=201, dependencies=[Depends(require_admin)])
def duplicate(id: int, db: Session = Depends(get_db), user=Depends(require_admin)):
    data = deepcopy(load(db, RouteTemplate, id).data)
    data['name'] = (data['name'][:150] + ' (cópia)')
    item = RouteTemplate(data=data, created_by=user.id)
    db.add(item)
    db.commit()
    return output(item)


@router.post('/route-templates/{id}/calculate', dependencies=[Depends(require_admin)])
def calculate(id: int, payload: CalculateInput, db: Session = Depends(get_db)):
    item = load(db, RouteTemplate, id)
    if item.revision != payload.revision:
        raise HTTPException(409, 'Recarregue a rota antes de calcular')
    data = deepcopy(item.data)
    stops = ([{**point, 'invoices': []} for point in data['addresses']] if data['addresses'] else
             [{**n['destination'], 'invoices': [n['number']]} for n in data['invoices']])
    if not data['origin'] or not stops:
        raise HTTPException(422, 'Informe origem e ao menos uma parada')
    origin, end = data['origin'], data['return_point'] or data['origin']
    points = [origin] + stops
    order = list(range(1, len(points)))
    if payload.optimize:
        # The final matrix node is the return address. Fold its edge costs into
        # origin's column to reuse the exact existing circuit solver (<=10).
        matrix = provider.matrix(points + [end])
        cost = [row[:-1] for row in matrix['durations' if data['objective'] == 'duration' else 'distances'][:-1]]
        for i in range(1, len(points)):
            cost[i][0] = matrix['durations' if data['objective'] == 'duration' else 'distances'][i][-1]
        if len(stops) <= 10:
            order = provider.optimal_order(cost)
        else:
            # Bounded nearest-neighbour heuristic for address-only routes.
            order, remaining, current = [], set(order), 0
            while remaining:
                current = min(remaining, key=lambda j: (cost[current][j], j))
                order.append(current)
                remaining.remove(current)
    result = provider.geometry([origin] + [points[i] for i in order] + [end])
    if not all(isfinite(result[k]) and result[k] >= 0 for k in ('distance', 'duration')):
        raise HTTPException(422, 'Estimativa inválida do provedor')
    data['stops'] = [stops[i-1] for i in order]
    if data['addresses']:
        data['addresses'] = [{k: s[k] for k in ('address', 'latitude', 'longitude')} for s in data['stops']]
    else:
        notes = {n['number']: n for n in data['invoices']}
        data['invoices'] = [notes[n] for s in data['stops'] for n in s['invoices']]
    data['result'] = {**result, 'provider': 'osrm', 'return_to_origin': origin == end,
                      'warning': WARNING if data['profile'] == 'truck' else None,
                      'truck_restrictions_supported': False,
                      'algorithm': 'manual' if not payload.optimize else 'held-karp' if len(stops) <= 10 else 'nearest-neighbour'}
    return write_template(db, item, payload.revision, data)


def execution_output(db, item):
    plan = load(db, RoutePlan, item.plan_id)
    # SQLite returns naive timestamps; persisted values are always UTC.
    from datetime import UTC
    start = item.starts_at.replace(tzinfo=UTC) if item.starts_at.tzinfo is None else item.starts_at
    return {'id': item.id, 'revision': item.revision, 'template_id': item.template_id,
            'template_revision': plan.data['template_revision'], 'plan_id': item.plan_id,
            'name': plan.data['name'], 'date': start.astimezone(LOCAL).date(),
            'departure_time': item.departure_time, 'driver_id': item.driver_id, 'vehicle_id': item.vehicle_id,
            'driver_name': db.get(Driver, item.driver_id).nome, 'vehicle_plate': db.get(Vehicle, item.vehicle_id).placa,
            'status': execution_status(db, item), 'notes': item.notes, 'trip_id': plan.data.get('trip_id'),
            'snapshot': deepcopy(plan.data), 'request_key': item.request_key}


@router.get('/route-executions', dependencies=[Depends(require_admin)])
def list_executions(date_from: date, date_to: date, driver_id: int | None = None,
                    vehicle_id: int | None = None, status: str | None = None, db: Session = Depends(get_db)):
    if date_to < date_from or (date_to-date_from).days > 90:
        raise HTTPException(422, 'Selecione um intervalo de até 90 dias')
    # Convert explicitly to UTC: SQLite's timezone-aware DateTime drops offsets.
    from datetime import UTC
    stmt = select(RouteExecution).where(
        RouteExecution.starts_at >= datetime.combine(date_from, time.min, LOCAL).astimezone(UTC),
        RouteExecution.starts_at < datetime.combine(date_to+timedelta(days=1), time.min, LOCAL).astimezone(UTC))
    if driver_id:
        stmt = stmt.where(RouteExecution.driver_id == driver_id)
    if vehicle_id:
        stmt = stmt.where(RouteExecution.vehicle_id == vehicle_id)
    stmt = stmt.join(RouteTemplate, RouteExecution.template_id == RouteTemplate.id).where(
        RouteTemplate.data['deleted'].as_boolean().is_not(True))
    if status is None:
        stmt = stmt.where(RouteExecution.status != 'CANCELADA')
    rows = [execution_output(db, item) for item in db.scalars(stmt.order_by(RouteExecution.starts_at, RouteExecution.id))]
    return [row for row in rows if status is None or row['status'] == status]


@router.get('/route-executions/{id}', dependencies=[Depends(require_admin)])
def execution_detail(id: int, db: Session = Depends(get_db)):
    return execution_output(db, load(db, RouteExecution, id))


@router.post('/route-executions', status_code=201, dependencies=[Depends(require_admin)])
def schedule(payload: ExecutionInput, db: Session = Depends(get_db), user=Depends(require_admin)):
    existing = db.scalar(select(RouteExecution).where(RouteExecution.request_key == payload.request_key))
    if existing:
        out = execution_output(db, existing)
        if any(out[key] != value for key, value in {
            'template_id': payload.template_id, 'template_revision': payload.template_revision,
            'date': payload.date, 'driver_id': payload.driver_id, 'vehicle_id': payload.vehicle_id,
            'departure_time': payload.departure_time.strftime('%H:%M') if payload.departure_time else None,
            'notes': payload.notes}.items()):
            raise HTTPException(409, 'Chave de programação já utilizada com outros dados')
        return out
    template = load(db, RouteTemplate, payload.template_id)
    if not template.data['active'] or not template.data['result']:
        raise HTTPException(422, 'Ative e calcule a rota antes de programar')
    if template.revision != payload.template_revision:
        raise HTTPException(409, 'Rota alterada. Recarregue antes de programar')
    if payload.date < today():
        raise HTTPException(422, 'Não é possível programar em data passada')
    snapshot = deepcopy(template.data)
    start, end = check_conflicts(db, payload, snapshot)
    snapshot.update(template_id=template.id, template_revision=template.revision,
                    driver_id=payload.driver_id, vehicle_id=payload.vehicle_id,
                    execution_date=payload.date.isoformat(), execution_notes=payload.notes,
                    departure_time=payload.departure_time.strftime('%H:%M') if payload.departure_time else None)
    plan = RoutePlan(data=snapshot, status='CONFIRMADO', created_by=user.id)
    db.add(plan)
    try:
        db.flush()
        db.add(RoutePlanVersion(plan_id=plan.id, revision=0, data={'status': 'CONFIRMADO', **deepcopy(snapshot)}, created_by=user.id))
        execution = RouteExecution(template_id=template.id, plan_id=plan.id, driver_id=payload.driver_id,
            vehicle_id=payload.vehicle_id, starts_at=start, ends_at=end, notes=payload.notes,
            departure_time=payload.departure_time.strftime('%H:%M') if payload.departure_time else None,
            request_key=payload.request_key, created_by=user.id)
        db.add(execution)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, 'Programação já registrada. Atualize a semana') from exc
    return execution_output(db, execution)


@router.put('/route-executions/{id}', dependencies=[Depends(require_admin)])
def reschedule(id: int, payload: ExecutionInput, db: Session = Depends(get_db)):
    item = load(db, RouteExecution, id)
    plan = load(db, RoutePlan, item.plan_id)
    if execution_status(db, item) != 'PROGRAMADA' or item.revision != payload.revision:
        raise HTTPException(409, 'Execução iniciada, cancelada ou alterada')
    if payload.template_id != item.template_id or payload.template_revision != plan.data['template_revision']:
        raise HTTPException(422, 'O percurso da execução não pode ser substituído')
    if payload.date < today():
        raise HTTPException(422, 'Não é possível reagendar em data passada')
    start, end = check_conflicts(db, payload, plan.data, item.id)
    # Lock the plan through an atomic update; trip creation claims the same row.
    claimed = db.execute(update(RoutePlan).where(RoutePlan.id == plan.id,
        RoutePlan.data['trip_id'].as_integer().is_(None), RoutePlan.revision == plan.revision,
        RoutePlan.status == 'CONFIRMADO').values(data={**plan.data, 'driver_id': payload.driver_id,
        'vehicle_id': payload.vehicle_id, 'execution_date': payload.date.isoformat(), 'execution_notes': payload.notes,
        'departure_time': payload.departure_time.strftime('%H:%M') if payload.departure_time else None},
        revision=plan.revision+1), execution_options={'synchronize_session': False})
    changed = db.execute(update(RouteExecution).where(RouteExecution.id == id, RouteExecution.revision == payload.revision,
        RouteExecution.status == 'PROGRAMADA').values(starts_at=start, ends_at=end,
        driver_id=payload.driver_id, vehicle_id=payload.vehicle_id, notes=payload.notes,
        departure_time=payload.departure_time.strftime('%H:%M') if payload.departure_time else None,
        revision=payload.revision+1), execution_options={'synchronize_session': False})
    if claimed.rowcount != 1 or changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'Programação alterada ou iniciada. Recarregue')
    db.commit()
    db.refresh(item)
    db.refresh(plan)
    return execution_output(db, item)


@router.post('/route-executions/{id}/cancel', dependencies=[Depends(require_admin)])
def cancel(id: int, payload: RevisionInput, db: Session = Depends(get_db)):
    item = load(db, RouteExecution, id)
    plan = load(db, RoutePlan, item.plan_id)
    if execution_status(db, item) != 'PROGRAMADA' or item.revision != payload.revision:
        raise HTTPException(409, 'Somente execuções ainda não iniciadas podem ser canceladas')
    result = execution_output(db, item)
    if not remove_unstarted_execution(db, item):
        raise HTTPException(409, 'Viagem ja iniciada. A programacao nao pode ser excluida')
    db.commit()
    return {**result, 'status': 'CANCELADA'}
