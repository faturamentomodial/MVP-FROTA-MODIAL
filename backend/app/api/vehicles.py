from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_admin
from app.core.database import get_db
from app.models import User, Vehicle
from app.models.enums import UserRole, VehicleStatus
from app.repositories.pagination import paginate
from app.schemas import ActiveUpdate, Page, VehicleCreate, VehicleOut, VehicleUpdate
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

