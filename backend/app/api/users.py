from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models import User
from app.models.enums import UserRole
from app.schemas import ActiveUpdate, UserOut
from app.services.audit import audit


router = APIRouter(prefix="/users", tags=["Gestores"])


class ManagerFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome: str = Field(min_length=2, max_length=160)
    email: EmailStr
    ativo: bool = True

    @field_validator("nome", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class ManagerCreate(ManagerFields):
    # Preserve the password exactly as entered, including any spaces.
    senha: str = Field(min_length=8, max_length=128)

class ManagerUpdate(ManagerFields):
    senha: str | None = Field(default=None, min_length=8, max_length=128)

def manager_or_404(db: Session, user_id: int) -> User:
    account = db.scalar(select(User).where(User.id == user_id, User.role == UserRole.ADMIN))
    if not account:
        raise HTTPException(status_code=404, detail="Gestor não encontrado")
    return account


def persist(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="E-mail já cadastrado") from exc


def check_email(db: Session, email: str, user_id: int | None = None) -> None:
    stmt = select(User.id).where(func.lower(User.email) == email.lower())
    if user_id is not None:
        stmt = stmt.where(User.id != user_id)
    if db.scalar(stmt) is not None:
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")


def check_status(account: User, active: bool, actor: User) -> None:
    if not active and account.id == actor.id:
        raise HTTPException(status_code=400, detail="Você não pode desativar seu próprio acesso")


@router.get("", response_model=list[UserOut])
def list_managers(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return list(db.scalars(select(User).where(User.role == UserRole.ADMIN).order_by(User.nome, User.id)))


@router.post("", response_model=UserOut, status_code=201)
def create_manager(payload: ManagerCreate, db: Session = Depends(get_db), actor: User = Depends(require_admin)):
    check_email(db, str(payload.email))
    account = User(nome=payload.nome, email=str(payload.email).lower(), senha_hash=get_password_hash(payload.senha), role=UserRole.ADMIN, ativo=payload.ativo)
    db.add(account)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="E-mail já cadastrado") from exc
    audit(db, actor, "CRIAR", "USER", account.id)
    persist(db)
    return account


@router.put("/{user_id}", response_model=UserOut)
def update_manager(user_id: int, payload: ManagerUpdate, db: Session = Depends(get_db), actor: User = Depends(require_admin)):
    account = manager_or_404(db, user_id)
    check_status(account, payload.ativo, actor)
    check_email(db, str(payload.email), account.id)
    account.nome = payload.nome
    account.email = str(payload.email).lower()
    account.ativo = payload.ativo
    if payload.senha is not None:
        account.senha_hash = get_password_hash(payload.senha)
    audit(db, actor, "ALTERAR", "USER", account.id, {"senha_alterada": payload.senha is not None})
    persist(db)
    return account


@router.patch("/{user_id}/status", response_model=UserOut)
def set_manager_status(user_id: int, payload: ActiveUpdate, db: Session = Depends(get_db), actor: User = Depends(require_admin)):
    account = manager_or_404(db, user_id)
    check_status(account, payload.ativo, actor)
    account.ativo = payload.ativo
    audit(db, actor, "ATIVAR" if payload.ativo else "DESATIVAR", "USER", account.id)
    persist(db)
    return account
