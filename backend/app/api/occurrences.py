from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import get_current_user, require_admin, require_driver
from app.api.helpers import occurrence_dict
from app.core.database import get_db
from app.models import Occurrence, User
from app.models.enums import OccurrenceStatus, OccurrenceType, TripStatus, UserRole
from app.repositories.pagination import paginate
from app.schemas import OccurrenceCreate, OccurrenceOut, OccurrenceUpdate, Page
from app.services.audit import audit
from app.services.trips import get_driver_for_user, load_trip


router = APIRouter(prefix="/occurrences", tags=["Ocorrências"])


def occurrence_query():
    return select(Occurrence).options(joinedload(Occurrence.driver), joinedload(Occurrence.vehicle))


@router.post("", response_model=OccurrenceOut, status_code=201)
def create(payload: OccurrenceCreate, db: Session = Depends(get_db), user: User = Depends(require_driver)):
    trip = load_trip(db, payload.trip_id)
    driver = get_driver_for_user(db, user)
    if trip.driver_id != driver.id:
        raise HTTPException(status_code=403, detail="Esta viagem pertence a outro motorista")
    if trip.status != TripStatus.EM_ANDAMENTO:
        raise HTTPException(status_code=400, detail="Ocorrência só pode ser registrada em viagem em andamento")
    occurrence = Occurrence(
        trip_id=trip.id,
        driver_id=trip.driver_id,
        vehicle_id=trip.vehicle_id,
        tipo=payload.tipo,
        descricao=payload.descricao,
        local=payload.local,
    )
    db.add(occurrence)
    db.flush()
    audit(db, user, "CRIAR", "OCCURRENCE", occurrence.id, {"trip_id": trip.id, "tipo": payload.tipo.value})
    db.commit()
    item = db.scalar(occurrence_query().where(Occurrence.id == occurrence.id))
    return occurrence_dict(item)


@router.get("", response_model=Page[OccurrenceOut])
def list_occurrences(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    driver_id: int | None = None,
    vehicle_id: int | None = None,
    trip_id: int | None = None,
    tipo: OccurrenceType | None = None,
    status_filter: OccurrenceStatus | None = Query(None, alias="status"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    stmt = occurrence_query().order_by(Occurrence.data_hora.desc())
    for condition in (
        Occurrence.driver_id == driver_id if driver_id else None,
        Occurrence.vehicle_id == vehicle_id if vehicle_id else None,
        Occurrence.trip_id == trip_id if trip_id else None,
        Occurrence.tipo == tipo if tipo else None,
        Occurrence.status == status_filter if status_filter else None,
        Occurrence.data_hora >= date_from if date_from else None,
        Occurrence.data_hora <= date_to if date_to else None,
    ):
        if condition is not None:
            stmt = stmt.where(condition)
    items, total, pages = paginate(db, stmt, page, page_size)
    return {"items": [occurrence_dict(item) for item in items], "total": total, "page": page, "page_size": page_size, "pages": pages}


@router.get("/{occurrence_id}", response_model=OccurrenceOut)
def get(occurrence_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.scalar(occurrence_query().where(Occurrence.id == occurrence_id))
    if not item:
        raise HTTPException(status_code=404, detail="Ocorrência não encontrada")
    if user.role == UserRole.MOTORISTA and item.driver_id != get_driver_for_user(db, user).id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return occurrence_dict(item)


@router.patch("/{occurrence_id}", response_model=OccurrenceOut)
def update(occurrence_id: int, payload: OccurrenceUpdate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    item = db.scalar(occurrence_query().where(Occurrence.id == occurrence_id))
    if not item:
        raise HTTPException(status_code=404, detail="Ocorrência não encontrada")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    audit(db, user, "ALTERAR_STATUS", "OCCURRENCE", item.id, {"status": item.status.value})
    db.commit()
    db.refresh(item)
    return occurrence_dict(item)
