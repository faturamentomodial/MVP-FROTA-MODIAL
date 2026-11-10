from datetime import UTC, datetime
from typing import Literal
from sqlalchemy import case, func
from app.models import Occurrence
from app.models.enums import OccurrenceStatus
from app.api.helpers import occurrence_dict
from app.api.occurrences import occurrence_query
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.core.database import get_db
from app.models import User, Vehicle
from app.models.enums import UserRole, VehicleStatus
from app.repositories.pagination import paginate
from app.schemas import OccurrenceOut, ActiveUpdate, Page, VehicleCreate, VehicleOut, VehicleUpdate
from app.services.audit import audit


router = APIRouter(prefix="/vehicles", tags=["Veículos"])


@router.get("", response_model=Page[VehicleOut])
def list_vehicles(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    available: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == UserRole.COMPRAS:
        raise HTTPException(403, "Acesso não autorizado para este perfil")
    stmt = select(Vehicle).order_by(Vehicle.placa)
    if user.role == UserRole.MOTORISTA or available:
        stmt = stmt.where(Vehicle.ativo.is_(True), Vehicle.status == VehicleStatus.DISPONIVEL)
    if search:
        stmt = stmt.where(or_(Vehicle.placa.ilike(f"%{search}%"), Vehicle.modelo.ilike(f"%{search}%")))
    items, total, pages = paginate(db, stmt, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size, "pages": pages}


@router.post("", response_model=VehicleOut, status_code=201)
def create_vehicle(payload: VehicleCreate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    vehicle = Vehicle(**payload.model_dump())
    if not vehicle.ativo:
        vehicle.status = VehicleStatus.INATIVO
    db.add(vehicle)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Placa já cadastrada") from exc
    audit(db, user, "CRIAR", "VEHICLE", vehicle.id)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.get("/{vehicle_id}", response_model=VehicleOut)
def get_vehicle(vehicle_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Veículo não encontrado")
    return vehicle


@router.put("/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(vehicle_id: int, payload: VehicleUpdate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    vehicle = db.get(Vehicle, vehicle_id)
    if not vehicle:
        raise HTTPException(status_code=404, detail="Veículo não encontrado")
    data = payload.model_dump(exclude_unset=True)
    if vehicle.status == VehicleStatus.EM_VIAGEM and (data.get("ativo") is False or data.get("status") not in (None, VehicleStatus.EM_VIAGEM)):
        raise HTTPException(status_code=409, detail="Não é possível alterar o status de veículo em viagem")
    for key, value in data.items():
        setattr(vehicle, key, value)
    if data.get("ativo") is False:
        vehicle.status = VehicleStatus.INATIVO
    elif data.get("ativo") is True and vehicle.status == VehicleStatus.INATIVO:
        vehicle.status = VehicleStatus.DISPONIVEL
    audit(db, user, "ALTERAR", "VEHICLE", vehicle.id)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Placa já cadastrada") from exc
    db.refresh(vehicle)
    return vehicle


@router.patch("/{vehicle_id}/status", response_model=VehicleOut)
def set_vehicle_status(vehicle_id: int, payload: ActiveUpdate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return update_vehicle(vehicle_id, VehicleUpdate(ativo=payload.ativo), db, user)



@router.get("/{vehicle_id}/maintenance")
def vehicle_maintenance(
    vehicle_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    maintenance_type: Literal["PREVENTIVA", "CORRETIVA", "EMERGENCIAL"] | None = None,
    status_filter: OccurrenceStatus | None = Query(None, alias="status"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if not db.get(Vehicle, vehicle_id):
        raise HTTPException(404, "Veículo não encontrado")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Período inválido")
    base = (Occurrence.vehicle_id == vehicle_id, Occurrence.maintenance_type.is_not(None))
    summary = db.execute(select(
        func.count(Occurrence.id),
        func.sum(case((Occurrence.status.in_([OccurrenceStatus.ABERTA, OccurrenceStatus.EM_ANALISE]), 1), else_=0)),
        func.max(case((Occurrence.status == OccurrenceStatus.RESOLVIDA, Occurrence.maintenance_completed_at))),
        func.coalesce(func.sum(Occurrence.maintenance_cost), 0),
    ).where(*base)).one()
    stmt = occurrence_query().where(*base)
    for condition in (
        Occurrence.maintenance_type == maintenance_type if maintenance_type else None,
        Occurrence.status == status_filter if status_filter else None,
        Occurrence.data_hora >= date_from if date_from else None,
        Occurrence.data_hora <= date_to if date_to else None,
    ):
        if condition is not None:
            stmt = stmt.where(condition)
    items, total, pages = paginate(db, stmt.order_by(Occurrence.data_hora.desc(), Occurrence.id.desc()), page, page_size)
    return {"items": [OccurrenceOut.model_validate(occurrence_dict(item)).model_dump(mode="json") for item in items], "total": total,
            "page": page, "page_size": page_size, "pages": pages,
            "summary": {"total": summary[0], "pending": summary[1] or 0,
                        "last_completed_at": summary[2].replace(tzinfo=UTC) if summary[2] and summary[2].tzinfo is None else summary[2], "cost": summary[3]}}
