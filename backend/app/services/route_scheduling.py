from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select, update, or_
from app.models import Driver, Vehicle, Trip
from app.models.route_plans import RoutePlan
from app.models.route_templates import RouteExecution

LOCAL = ZoneInfo('America/Sao_Paulo')


def today():
    return datetime.now(LOCAL).date()


def execution_status(db, execution):
    if execution.status == 'CANCELADA':
        return 'CANCELADA'
    plan = db.get(RoutePlan, execution.plan_id)
    trip = db.get(Trip, plan.data.get('trip_id')) if plan.data.get('trip_id') else None
    if trip:
        return {'ABERTA': 'EM_ANDAMENTO', 'EM_ANDAMENTO': 'EM_ANDAMENTO',
                'FINALIZADA': 'FINALIZADA', 'CANCELADA': 'CANCELADA'}[trip.status.value]
    return 'PROGRAMADA'


def interval(payload, snapshot):
    start = datetime.combine(payload.date, payload.departure_time or time.min, LOCAL)
    # Without a departure time, reserve the full local day. Timed routes include
    # one hour for loading/unloading beyond the provider's driving estimate.
    end = (start + timedelta(seconds=snapshot['result']['duration'], hours=1)
           if payload.departure_time else datetime.combine(payload.date + timedelta(days=1), time.min, LOCAL))
    return start.astimezone(UTC), end.astimezone(UTC)


def check_conflicts(db, payload, snapshot, exclude_id=None):
    # Resource writes serialize competing bookings on SQLite and PostgreSQL.
    # Every booking acquires resources in the same order, before reading bookings.
    for model, resource_id in ((Driver, payload.driver_id), (Vehicle, payload.vehicle_id)):
        db.execute(update(model).where(model.id == resource_id).values(ativo=model.ativo))
        resource = db.get(model, resource_id, populate_existing=True)
        if not resource or not resource.ativo or (model is Driver and not resource.user.ativo):
            raise HTTPException(422, 'Selecione motorista e veículo ativos')
    start, end = interval(payload, snapshot)
    candidates = db.scalars(select(RouteExecution).where(
        RouteExecution.id != exclude_id if exclude_id is not None else True,
        or_(RouteExecution.driver_id == payload.driver_id, RouteExecution.vehicle_id == payload.vehicle_id),
        RouteExecution.starts_at < end, RouteExecution.ends_at > start,
    ))
    if any(execution_status(db, item) not in ('CANCELADA', 'FINALIZADA') for item in candidates):
        raise HTTPException(409, 'Motorista ou veículo já reservado neste intervalo')
    return start, end


def is_execution_plan(db, plan_id):
    return db.scalar(select(RouteExecution.id).where(RouteExecution.plan_id == plan_id)) is not None
