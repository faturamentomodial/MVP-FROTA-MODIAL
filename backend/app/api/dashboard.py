from datetime import UTC, datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.core.database import get_db
from app.models import Checklist, Driver, Occurrence, Trip, TripInvoice, User, Vehicle
from app.models.enums import ChecklistStatus, OccurrenceStatus, OccurrenceType, TripStatus, VehicleStatus
from app.schemas import DashboardOut


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def apply_trip_filters(stmt, date_from, date_to, driver_id, vehicle_id):
    if date_from:
        stmt = stmt.where(Trip.data_saida >= date_from)
    if date_to:
        stmt = stmt.where(Trip.data_saida <= date_to)
    if driver_id:
        stmt = stmt.where(Trip.driver_id == driver_id)
    if vehicle_id:
        stmt = stmt.where(Trip.vehicle_id == vehicle_id)
    return stmt


@router.get("", response_model=DashboardOut)
def dashboard(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    driver_id: int | None = None,
    vehicle_id: int | None = None,
    occurrence_type: OccurrenceType | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    now = datetime.now(UTC)
    today = datetime.combine(now.date(), time.min, tzinfo=UTC)
    week = today - timedelta(days=today.weekday())
    month = today.replace(day=1)

    vehicle_stmt = select(
        func.count(Vehicle.id),
        func.sum(case((Vehicle.status == VehicleStatus.DISPONIVEL, 1), else_=0)),
        func.sum(case((Vehicle.status == VehicleStatus.EM_VIAGEM, 1), else_=0)),
        func.sum(case((Vehicle.status == VehicleStatus.ATENCAO, 1), else_=0)),
        func.sum(case((Vehicle.status == VehicleStatus.INATIVO, 1), else_=0)),
    )
    if vehicle_id:
        vehicle_stmt = vehicle_stmt.where(Vehicle.id == vehicle_id)
    fleet = db.execute(vehicle_stmt).one()

    trip_base = apply_trip_filters(select(Trip.id), date_from, date_to, driver_id, vehicle_id).subquery()
    trip_metrics = db.execute(
        select(func.count(Trip.id), func.coalesce(func.sum(Trip.km_percorrido), 0)).where(Trip.id.in_(select(trip_base.c.id)))
    ).one()

    checklist_filter = select(Checklist).where(Checklist.trip_id.in_(select(trip_base.c.id))).subquery()
    checklist_metrics = db.execute(
        select(
            func.count(checklist_filter.c.id),
            func.sum(case((checklist_filter.c.status == ChecklistStatus.COM_PROBLEMAS, 1), else_=0)),
        )
    ).one()

    def checklist_since(start: datetime) -> int:
        stmt = select(func.count(Checklist.id)).join(Trip, Trip.id == Checklist.trip_id).where(Checklist.data_hora >= start)
        if driver_id:
            stmt = stmt.where(Checklist.driver_id == driver_id)
        if vehicle_id:
            stmt = stmt.where(Checklist.vehicle_id == vehicle_id)
        return db.scalar(stmt) or 0

    occurrence_stmt = select(
        func.count(Occurrence.id),
        func.sum(case((Occurrence.status == OccurrenceStatus.ABERTA, 1), else_=0)),
        func.sum(case((Occurrence.status == OccurrenceStatus.EM_ANALISE, 1), else_=0)),
        func.sum(case((Occurrence.status == OccurrenceStatus.RESOLVIDA, 1), else_=0)),
    ).where(Occurrence.trip_id.in_(select(trip_base.c.id)))
    if occurrence_type:
        occurrence_stmt = occurrence_stmt.where(Occurrence.tipo == occurrence_type)
    occurrence_metrics = db.execute(occurrence_stmt).one()

    series_stmt = (
        select(func.date(Checklist.data_hora).label("day"), func.count(Checklist.id).label("total"))
        .where(Checklist.trip_id.in_(select(trip_base.c.id)))
        .group_by(func.date(Checklist.data_hora))
        .order_by(func.date(Checklist.data_hora))
    )
    checklist_series = [{"date": str(row.day), "total": row.total} for row in db.execute(series_stmt).all()]

    type_stmt = (
        select(Occurrence.tipo, func.count(Occurrence.id).label("total"))
        .where(Occurrence.trip_id.in_(select(trip_base.c.id)))
        .group_by(Occurrence.tipo)
        .order_by(func.count(Occurrence.id).desc())
    )
    if occurrence_type:
        type_stmt = type_stmt.where(Occurrence.tipo == occurrence_type)
    occurrence_by_type = [{"type": row.tipo.value, "total": row.total} for row in db.execute(type_stmt).all()]

    trip_agg = (
        select(
            Trip.driver_id.label("driver_id"),
            func.count(Trip.id).label("trips"),
            func.coalesce(func.sum(Trip.km_percorrido), 0).label("km"),
        )
        .where(Trip.id.in_(select(trip_base.c.id)))
        .group_by(Trip.driver_id)
        .subquery()
    )
    checklist_agg = (
        select(Checklist.driver_id.label("driver_id"), func.count(Checklist.id).label("checklists"))
        .where(Checklist.trip_id.in_(select(trip_base.c.id)))
        .group_by(Checklist.driver_id)
        .subquery()
    )
    occurrence_agg = (
        select(Occurrence.driver_id.label("driver_id"), func.count(Occurrence.id).label("occurrences"))
        .where(Occurrence.trip_id.in_(select(trip_base.c.id)))
        .group_by(Occurrence.driver_id)
        .subquery()
    )
    driver_stmt = (
        select(
            Driver.id,
            Driver.nome,
            func.coalesce(trip_agg.c.trips, 0),
            func.coalesce(checklist_agg.c.checklists, 0),
            func.coalesce(occurrence_agg.c.occurrences, 0),
            func.coalesce(trip_agg.c.km, 0),
        )
        .outerjoin(trip_agg, trip_agg.c.driver_id == Driver.id)
        .outerjoin(checklist_agg, checklist_agg.c.driver_id == Driver.id)
        .outerjoin(occurrence_agg, occurrence_agg.c.driver_id == Driver.id)
        .order_by(func.coalesce(trip_agg.c.km, 0).desc())
        .limit(100)
    )
    if driver_id:
        driver_stmt = driver_stmt.where(Driver.id == driver_id)
    drivers = [
        {"id": row[0], "name": row[1], "trips": row[2], "checklists": row[3], "occurrences": row[4], "km": row[5]}
        for row in db.execute(driver_stmt).all()
    ]

    vehicle_trip_agg = (
        select(Trip.vehicle_id.label("vehicle_id"), func.count(Trip.id).label("trips"))
        .where(Trip.id.in_(select(trip_base.c.id)))
        .group_by(Trip.vehicle_id)
        .subquery()
    )
    vehicle_occ_agg = (
        select(Occurrence.vehicle_id.label("vehicle_id"), func.count(Occurrence.id).label("occurrences"))
        .where(Occurrence.trip_id.in_(select(trip_base.c.id)))
        .group_by(Occurrence.vehicle_id)
        .subquery()
    )
    vehicle_table_stmt = (
        select(
            Vehicle.id,
            Vehicle.placa,
            Vehicle.modelo,
            Vehicle.status,
            Vehicle.km_atual,
            func.coalesce(vehicle_trip_agg.c.trips, 0),
            func.coalesce(vehicle_occ_agg.c.occurrences, 0),
        )
        .outerjoin(vehicle_trip_agg, vehicle_trip_agg.c.vehicle_id == Vehicle.id)
        .outerjoin(vehicle_occ_agg, vehicle_occ_agg.c.vehicle_id == Vehicle.id)
        .order_by(Vehicle.placa)
        .limit(100)
    )
    if vehicle_id:
        vehicle_table_stmt = vehicle_table_stmt.where(Vehicle.id == vehicle_id)
    vehicles = [
        {"id": row[0], "plate": row[1], "model": row[2], "status": row[3].value, "km": row[4], "trips": row[5], "occurrences": row[6]}
        for row in db.execute(vehicle_table_stmt).all()
    ]

    route_stmt = select(
        Trip.id, Driver.nome.label("driver_name"),
        func.count(TripInvoice.id).label("total"),
        func.sum(case((TripInvoice.status == "ENTREGUE", 1), else_=0)).label("delivered"),
        func.sum(case((TripInvoice.status == "NAO_ENTREGUE", 1), else_=0)).label("failed"),
        func.sum(case((TripInvoice.status.in_(("PENDENTE", "EM_ENTREGA")), 1), else_=0)).label("pending"),
        func.max(TripInvoice.delivered_at).label("last_delivered_at"),
    ).join(Driver, Driver.id == Trip.driver_id).outerjoin(TripInvoice, TripInvoice.trip_id == Trip.id).where(
        Trip.id.in_(select(trip_base.c.id))
    ).group_by(Trip.id, Driver.nome).order_by(Trip.id.desc()).limit(100)
    delivery_routes = [dict(row._mapping) for row in db.execute(route_stmt)]

    return {
        "delivery_routes": delivery_routes,
        "total_vehicles": fleet[0] or 0,
        "available_vehicles": fleet[1] or 0,
        "vehicles_in_trip": fleet[2] or 0,
        "vehicles_attention": fleet[3] or 0,
        "inactive_vehicles": fleet[4] or 0,
        "total_trips": trip_metrics[0] or 0,
        "total_checklists": checklist_metrics[0] or 0,
        "checklists_today": checklist_since(today),
        "checklists_this_week": checklist_since(week),
        "checklists_this_month": checklist_since(month),
        "checklists_with_problems": checklist_metrics[1] or 0,
        "total_occurrences": occurrence_metrics[0] or 0,
        "open_occurrences": occurrence_metrics[1] or 0,
        "in_analysis_occurrences": occurrence_metrics[2] or 0,
        "resolved_occurrences": occurrence_metrics[3] or 0,
        "total_km": trip_metrics[1] or 0,
        "checklist_series": checklist_series,
        "occurrence_by_type": occurrence_by_type,
        "drivers": drivers,
        "vehicles": vehicles,
    }

