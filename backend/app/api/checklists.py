from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.dependencies import get_current_user, require_admin, require_driver
from app.core.database import get_db
from app.models import Checklist, ChecklistAnswer, ChecklistItem, Trip, User
from app.models.enums import AnswerStatus, ChecklistStatus, TripStatus, UserRole
from app.schemas import (
    ActiveUpdate,
    ChecklistCreate,
    ChecklistItemCreate,
    ChecklistItemOut,
    ChecklistItemUpdate,
    ChecklistOut,
)
from app.services.audit import audit
from app.services.trips import get_driver_for_user, load_trip


router = APIRouter(tags=["Checklist"])


@router.get("/checklist-items", response_model=list[ChecklistItemOut])
def list_items(active_only: bool = True, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    stmt = select(ChecklistItem).order_by(ChecklistItem.ordem, ChecklistItem.nome)
    if active_only:
        stmt = stmt.where(ChecklistItem.ativo.is_(True))
    return list(db.scalars(stmt).all())


@router.post("/checklist-items", response_model=ChecklistItemOut, status_code=201)
def create_item(payload: ChecklistItemCreate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    item = ChecklistItem(**payload.model_dump())
    db.add(item)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Item de checklist já existe") from exc
    audit(db, user, "CRIAR", "CHECKLIST_ITEM", item.id)
    db.commit()
    db.refresh(item)
    return item


@router.put("/checklist-items/{item_id}", response_model=ChecklistItemOut)
def update_item(item_id: int, payload: ChecklistItemUpdate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    item = db.get(ChecklistItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, key, value)
    audit(db, user, "ALTERAR", "CHECKLIST_ITEM", item.id)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/checklist-items/{item_id}/status", response_model=ChecklistItemOut)
def set_item_status(item_id: int, payload: ActiveUpdate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    return update_item(item_id, ChecklistItemUpdate(ativo=payload.ativo), db, user)


@router.post("/trips/{trip_id}/checklist", response_model=ChecklistOut, status_code=201)
def submit_checklist(trip_id: int, payload: ChecklistCreate, db: Session = Depends(get_db), user: User = Depends(require_driver)):
    trip = load_trip(db, trip_id)
    driver = get_driver_for_user(db, user)
    if trip.driver_id != driver.id:
        raise HTTPException(status_code=403, detail="Esta viagem pertence a outro motorista")
    if trip.status != TripStatus.ABERTA:
        raise HTTPException(status_code=400, detail="Checklist permitido apenas antes do início da viagem")
    if trip.checklist:
        raise HTTPException(status_code=409, detail="Checklist já realizado")

    active_items = list(db.scalars(select(ChecklistItem).where(ChecklistItem.ativo.is_(True))).all())
    active_ids = {item.id for item in active_items}
    required_ids = {item.id for item in active_items if item.obrigatorio}
    answer_ids = [answer.checklist_item_id for answer in payload.answers]
    if len(answer_ids) != len(set(answer_ids)):
        raise HTTPException(status_code=400, detail="Não repita itens no checklist")
    if not set(answer_ids).issubset(active_ids):
        raise HTTPException(status_code=400, detail="Checklist contém item inválido ou inativo")
    missing = required_ids - set(answer_ids)
    if missing:
        raise HTTPException(status_code=400, detail="Todos os itens obrigatórios precisam ser respondidos")

    checklist_status = ChecklistStatus.COM_PROBLEMAS if any(a.status == AnswerStatus.PROBLEMA for a in payload.answers) else ChecklistStatus.APROVADO
    checklist = Checklist(
        trip_id=trip.id,
        driver_id=trip.driver_id,
        vehicle_id=trip.vehicle_id,
        status=checklist_status,
        observacao=payload.observacao,
    )
    checklist.answers = [ChecklistAnswer(**answer.model_dump()) for answer in payload.answers]
    db.add(checklist)
    audit(db, user, "FINALIZAR", "CHECKLIST", None, {"trip_id": trip.id, "status": checklist_status.value})
    db.commit()
    return db.scalar(select(Checklist).where(Checklist.id == checklist.id).options(selectinload(Checklist.answers).joinedload(ChecklistAnswer.item)))


@router.get("/checklists/{checklist_id}", response_model=ChecklistOut)
def get_checklist(checklist_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    checklist = db.scalar(select(Checklist).where(Checklist.id == checklist_id).options(selectinload(Checklist.answers).joinedload(ChecklistAnswer.item)))
    if not checklist:
        raise HTTPException(status_code=404, detail="Checklist não encontrado")
    if user.role == UserRole.MOTORISTA and checklist.driver_id != get_driver_for_user(db, user).id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return checklist

