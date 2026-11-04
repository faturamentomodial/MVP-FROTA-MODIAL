from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.core.database import get_db
from app.models import Pickup, User
from app.services.audit import audit


class PickupInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    nome: str = Field(min_length=2, max_length=160)
    telefone: str = Field(min_length=1, max_length=40)
    endereco: str = Field(min_length=1, max_length=500)


class PickupOut(PickupInput):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)
    id: int


router = APIRouter(prefix="/pickups", tags=["Coletas"])


@router.get("", response_model=list[PickupOut])
def list_pickups(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.scalars(select(Pickup).order_by(Pickup.nome, Pickup.id)).all()


@router.post("", response_model=PickupOut, status_code=201)
def create_pickup(payload: PickupInput, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    item = Pickup(**payload.model_dump())
    db.add(item)
    db.flush()
    audit(db, user, "CRIAR", "PICKUP", item.id)
    db.commit()
    db.refresh(item)
    return item


@router.put("/{pickup_id}", response_model=PickupOut)
def update_pickup(pickup_id: int, payload: PickupInput, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    item = db.get(Pickup, pickup_id)
    if not item:
        raise HTTPException(404, "Coleta n?o encontrada")
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    audit(db, user, "ALTERAR", "PICKUP", item.id)
    db.commit()
    db.refresh(item)
    return item
