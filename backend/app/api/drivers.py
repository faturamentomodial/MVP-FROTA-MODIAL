from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import require_admin
from app.api.helpers import driver_dict
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models import Driver, User
from app.models.enums import UserRole
from app.repositories.pagination import paginate
from app.schemas import ActiveUpdate, DriverCreate, DriverOut, DriverUpdate, Page
from app.services.audit import audit


router = APIRouter(prefix="/drivers", tags=["Motoristas"])


@router.get("", response_model=Page[DriverOut])
def list_drivers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    stmt = select(Driver).options(joinedload(Driver.user)).order_by(Driver.nome)
    if search:
        stmt = stmt.where(or_(Driver.nome.ilike(f"%{search}%"), Driver.cpf.ilike(f"%{search}%")))
    items, total, pages = paginate(db, stmt, page, page_size)
    return {"items": [driver_dict(item) for item in items], "total": total, "page": page, "page_size": page_size, "pages": pages}


@router.post("", response_model=DriverOut, status_code=201)
def create_driver(payload: DriverCreate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    account = User(nome=payload.nome, email=payload.email.lower(), senha_hash=get_password_hash(payload.senha), role=UserRole.MOTORISTA, ativo=payload.ativo)
    driver = Driver(nome=payload.nome, cpf=payload.cpf, telefone=payload.telefone, ativo=payload.ativo, user=account)
    db.add(driver)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="E-mail ou CPF já cadastrado") from exc
    audit(db, user, "CRIAR", "DRIVER", driver.id)
    db.commit()
    db.refresh(driver)
    return driver_dict(driver)


@router.get("/{driver_id}", response_model=DriverOut)
def get_driver(driver_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    driver = db.scalar(select(Driver).where(Driver.id == driver_id).options(joinedload(Driver.user)))
    if not driver:
        raise HTTPException(status_code=404, detail="Motorista não encontrado")
    return driver_dict(driver)


@router.put("/{driver_id}", response_model=DriverOut)
def update_driver(driver_id: int, payload: DriverUpdate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    driver = db.scalar(select(Driver).where(Driver.id == driver_id).options(joinedload(Driver.user)))
    if not driver:
        raise HTTPException(status_code=404, detail="Motorista não encontrado")
    data = payload.model_dump(exclude_unset=True)
    for key in ("nome", "cpf", "telefone", "ativo"):
        if key in data:
            setattr(driver, key, data[key])
    if "nome" in data:
        driver.user.nome = data["nome"]
    if "email" in data:
        driver.user.email = str(data["email"]).lower()
    if "senha" in data:
        driver.user.senha_hash = get_password_hash(data["senha"])
    if "ativo" in data:
        driver.user.ativo = data["ativo"]
    audit(db, user, "ALTERAR", "DRIVER", driver.id)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="E-mail ou CPF já cadastrado") from exc
    return driver_dict(driver)


@router.patch("/{driver_id}/status", response_model=DriverOut)
def set_driver_status(driver_id: int, payload: ActiveUpdate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return update_driver(driver_id, DriverUpdate(ativo=payload.ativo), db, user)

