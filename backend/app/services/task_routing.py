"""Insert accepted tasks into the driver's operational route atomically."""
from copy import deepcopy
from math import isfinite

from fastapi import HTTPException
from sqlalchemy import select, update

from app.models import TripInvoice
from app.models.enums import DeliveryStatus
from app.models.route_plans import RoutePlan, RoutePlanVersion
from app.services import route_planning as provider
from app.services.deliveries import claim_revision
from app.services.trips import get_active_trip


def insert_task(db, task, driver):
    trip = get_active_trip(db, driver.id)
    if trip is None:
        return
    plan = db.scalar(select(RoutePlan).where(RoutePlan.data['trip_id'].as_integer() == trip.id))
    if plan is None or not plan.data.get('origin'):
        raise HTTPException(409, 'A viagem precisa de uma rota com origem para receber tarefas')
    data = deepcopy(plan.data)
    candidates = provider.geocode(task.endereco)['candidates']
    if len(candidates) != 1:
        raise HTTPException(422, 'Informe um endereço mais preciso para a tarefa; não foi possível localizar uma única parada')
    point = {key: candidates[0][key] for key in ('latitude', 'longitude')}
    point['address'] = task.endereco
    label = f'Tarefa #{task.id}'
    point.update(task_id=task.id, title=task.titulo)
    addresses = data.get('addresses', [])
    notes = {n['number']: n['destination'] for n in data.get('invoices', [])}
    task_points = {f"Tarefa #{p['task_id']}": p for p in data.get('task_stops', [])}

    def destination(invoice):
        if invoice.numero_nota in task_points:
            return task_points[invoice.numero_nota]
        if invoice.is_address_stop and invoice.numero_nota.startswith('Parada '):
            return addresses[int(invoice.numero_nota.split()[-1]) - 1]
        return notes[invoice.numero_nota]

    invoices = sorted(trip.invoices, key=lambda n: (n.position, n.id))
    # Keep completed stops and the delivery currently being served in place.
    boundary = max((i + 1 for i, n in enumerate(invoices) if n.status != DeliveryStatus.PENDENTE), default=0)
    fixed, remaining = invoices[:boundary], invoices[boundary:]
    new = TripInvoice(trip_id=trip.id, numero_nota=label, volumes=0,
                      is_address_stop=True, status=DeliveryStatus.PENDENTE)
    pending = remaining + [new]
    start = destination(fixed[-1]) if fixed else data['origin']
    end = data.get('return_point') or data['origin']
    points = [start] + [point if n is new else destination(n) for n in pending] + [end]
    matrix = provider.matrix(points)
    costs = matrix['distances' if data.get('objective') == 'distance' else 'durations']
    cost = [row[:-1] for row in costs[:-1]]
    for i in range(1, len(cost)):
        cost[i][0] = costs[i][-1]
    order = provider.optimal_order(cost)
    result = provider.geometry([start] + [points[i] for i in order] + [end])
    if not all(isfinite(result[k]) and result[k] >= 0 for k in ('distance', 'duration')):
        raise HTTPException(422, 'Estimativa inválida do provedor')
    claim_revision(db, trip, trip.delivery_revision)
    db.add(new)
    for position, invoice in enumerate(fixed + [pending[i-1] for i in order], start=1):
        invoice.position = position
    data.setdefault('task_stops', []).append(point)
    data['stops'] = [destination(n) for n in fixed] + [points[i] for i in order]
    data['result'] = {**(data.get('result') or {}), **result, 'provider': 'osrm',
                      'algorithm': 'held-karp' if len(pending) <= 10 else 'nearest-neighbour',
                      'remaining_route': True}
    changed = db.execute(update(RoutePlan).where(RoutePlan.id == plan.id, RoutePlan.revision == plan.revision)
                         .values(data=data, revision=plan.revision + 1),
                         execution_options={'synchronize_session': False})
    if changed.rowcount != 1:
        raise HTTPException(409, 'A rota mudou. Atualize antes de aceitar a tarefa')
    db.add(RoutePlanVersion(plan_id=plan.id, revision=plan.revision + 1,
                           data={'status': plan.status, **data}, created_by=driver.user_id))


def resolve_task_stop(db, task, cancelled=False):
    """Task actions must not leave a pending stop blocking trip completion."""
    trip = get_active_trip(db, task.driver_id) if task.driver_id else None
    stop = next((n for n in trip.invoices if n.numero_nota == f'Tarefa #{task.id}'), None) if trip else None
    if stop and stop.status in (DeliveryStatus.PENDENTE, DeliveryStatus.EM_ENTREGA):
        from app.models.entities import utcnow
        claim_revision(db, trip, trip.delivery_revision)
        stop.status = DeliveryStatus.NAO_ENTREGUE if cancelled else DeliveryStatus.ENTREGUE
        if cancelled:
            stop.occurrence_at = utcnow()
            stop.occurrence_note = 'Tarefa cancelada'
        else:
            stop.delivered_at = utcnow()
