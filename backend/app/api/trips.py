from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.dependencies import get_current_user, require_admin, require_driver
from app.api.helpers import trip_dict
from app.core.database import get_db
from app.models import Checklist, Trip, TripInvoice, User
from app.models.enums import TripStatus, UserRole
from app.repositories.pagination import paginate
from app.schemas import DeliveryOrderIn, DeliveryOccurrenceIn, TripInvoiceOut, Page, TripCargoUpdate, TripCreate, TripFinish, TripOut
from app.services.audit import audit
from app.services.deliveries import claim_revision, reorder, transition
from app.services.trips import create_trip, finish_trip, get_active_trip, get_driver_for_user, load_trip, start_trip


router = APIRouter(prefix="/trips", tags=["Viagens"])


def ensure_trip_access(trip: Trip, user: User, db: Session) -> None:
    if user.role == UserRole.MOTORISTA and trip.driver_id != get_driver_for_user(db, user).id:
        raise HTTPException(status_code=403, detail="Esta viagem pertence a outro motorista")


@router.post("", response_model=TripOut, status_code=201)
def create(payload: TripCreate, db: Session = Depends(get_db), user: User = Depends(require_driver)):
    return trip_dict(create_trip(db, user, payload))


@router.get("/current", response_model=TripOut | None)
def current(db: Session = Depends(get_db), user: User = Depends(require_driver)):
    trip = get_active_trip(db, get_driver_for_user(db, user).id)
    if not trip:
        return None
    trip.occurrences
    return trip_dict(trip)


@router.get("", response_model=Page[TripOut])
def list_trips(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    driver_id: int | None = None,
    vehicle_id: int | None = None,
    status_filter: TripStatus | None = Query(None, alias="status"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    stmt = select(Trip).options(joinedload(Trip.driver), joinedload(Trip.vehicle), joinedload(Trip.checklist), selectinload(Trip.occurrences), selectinload(Trip.invoices)).order_by(Trip.data_saida.desc())
    if driver_id:
        stmt = stmt.where(Trip.driver_id == driver_id)
    if vehicle_id:
        stmt = stmt.where(Trip.vehicle_id == vehicle_id)
    if status_filter:
        stmt = stmt.where(Trip.status == status_filter)
    if date_from:
        stmt = stmt.where(Trip.data_saida >= date_from)
    if date_to:
        stmt = stmt.where(Trip.data_saida <= date_to)
    items, total, pages = paginate(db, stmt, page, page_size)
    return {"items": [trip_dict(item) for item in items], "total": total, "page": page, "page_size": page_size, "pages": pages}


@router.get("/{trip_id}", response_model=TripOut)
def get(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trip = load_trip(db, trip_id)
    ensure_trip_access(trip, user, db)
    return trip_dict(trip)


@router.post("/{trip_id}/start", response_model=TripOut)
def start(trip_id: int, db: Session = Depends(get_db), user: User = Depends(require_driver)):
    trip = load_trip(db, trip_id)
    ensure_trip_access(trip, user, db)
    return trip_dict(start_trip(db, trip, user))


@router.put("/{trip_id}/cargo", response_model=TripOut)
def update_cargo(trip_id: int, payload: TripCargoUpdate, db: Session = Depends(get_db), user: User = Depends(require_driver)):
    db.scalar(select(Trip.id).where(Trip.id == trip_id).with_for_update())
    trip = load_trip(db, trip_id)
    ensure_trip_access(trip, user, db)
    if trip.status != TripStatus.ABERTA:
        raise HTTPException(status_code=400, detail="A carga só pode ser alterada antes do início da viagem")
    claim_revision(db, trip, trip.delivery_revision)
    trip.invoices.clear()
    db.flush()
    trip.invoices.extend(
        TripInvoice(numero_nota=item.numero_nota, volumes=item.volumes, position=index)
        for index, item in enumerate(payload.notas, start=1)
    )
    audit(db, user, "ATUALIZAR_CARGA", "TRIP", trip.id, {"notas": len(payload.notas), "volumes": sum(item.volumes for item in payload.notas)})
    db.commit()
    return trip_dict(load_trip(db, trip.id))


@router.post("/{trip_id}/finish", response_model=TripOut)
def finish(trip_id: int, payload: TripFinish, db: Session = Depends(get_db), user: User = Depends(require_driver)):
    db.scalar(select(Trip.id).where(Trip.id == trip_id).with_for_update())
    trip = load_trip(db, trip_id)
    ensure_trip_access(trip, user, db)
    return trip_dict(finish_trip(db, trip, payload, user))


# Nested endpoints reuse existing trip ownership and invoice ordering.
def delivery_trip(db, trip_id, user, lock=False):
    if lock:
        db.scalar(select(Trip.id).where(Trip.id == trip_id).with_for_update())
    trip = load_trip(db, trip_id)
    ensure_trip_access(trip, user, db)
    return trip


@router.get("/{trip_id}/deliveries", response_model=list[TripInvoiceOut])
def deliveries(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return delivery_trip(db, trip_id, user).invoices


@router.get("/{trip_id}/deliveries/{invoice_id}", response_model=TripInvoiceOut)
def delivery(trip_id: int, invoice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trip = delivery_trip(db, trip_id, user)
    item = next((n for n in trip.invoices if n.id == invoice_id), None)
    if not item:
        raise HTTPException(404, "Entrega não encontrada nesta rota")
    return item


@router.post("/{trip_id}/deliveries/{invoice_id}/start", response_model=TripInvoiceOut)
def start_delivery(trip_id: int, invoice_id: int, db: Session = Depends(get_db), user: User = Depends(require_driver)):
    return transition(db, delivery_trip(db, trip_id, user, True), invoice_id, user, "start")


@router.post("/{trip_id}/deliveries/{invoice_id}/finish", response_model=TripInvoiceOut)
def finish_delivery(trip_id: int, invoice_id: int, db: Session = Depends(get_db), user: User = Depends(require_driver)):
    return transition(db, delivery_trip(db, trip_id, user, True), invoice_id, user, "finish")


@router.post("/{trip_id}/deliveries/{invoice_id}/occurrence", response_model=TripInvoiceOut)
def delivery_occurrence(trip_id: int, invoice_id: int, payload: DeliveryOccurrenceIn, db: Session = Depends(get_db), user: User = Depends(require_driver)):
    return transition(db, delivery_trip(db, trip_id, user, True), invoice_id, user, "occurrence", payload)


@router.put("/{trip_id}/delivery-order", response_model=TripOut)
def update_delivery_order(trip_id: int, payload: DeliveryOrderIn, db: Session = Depends(get_db), user: User = Depends(require_driver)):
    trip = delivery_trip(db, trip_id, user, True)
    reorder(db, trip, payload, user)
    db.expire_all()
    return trip_dict(load_trip(db, trip_id))
