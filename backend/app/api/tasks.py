from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from jwt import InvalidTokenError

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import get_current_user, require_operations, require_driver
from app.core.config import settings
from app.core.database import get_db
from app.models import Driver, Task, TaskStatus, User
from app.models.entities import utcnow
from app.models.enums import UserRole

router = APIRouter(prefix="/tasks", tags=["Central de Tarefas"])


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    titulo: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
    endereco: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    observacoes: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]


class TaskAcceptance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    location_token: str


def eligible_driver(user: User = Depends(require_driver), db: Session = Depends(get_db)) -> Driver:
    driver = db.scalar(select(Driver).where(Driver.user_id == user.id, Driver.ativo.is_(True)))
    if driver is None:
        raise HTTPException(403, "Motorista inativo ou sem cadastro autorizado")
    return driver


def task_dict(task: Task) -> dict:
    result = {column.name: getattr(task, column.name) for column in Task.__table__.columns}
    # SQLite returns naive datetimes; storage is always UTC.
    for key, value in result.items():
        if isinstance(value, datetime) and value.tzinfo is None:
            result[key] = value.replace(tzinfo=UTC)
    result["driver_name"] = task.driver.nome if task.driver else None
    return result


def find_task(db: Session, task_id: int) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(404, "Tarefa não encontrada")
    return task


@router.post("", status_code=201)
def create_task(body: TaskCreate, user: User = Depends(require_operations), db: Session = Depends(get_db)):
    task = Task(**body.model_dump(), created_by=user.id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task_dict(task)


@router.get("")
def admin_tasks(status: TaskStatus | None = None, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200), user: User = Depends(require_operations), db: Session = Depends(get_db)):
    query = select(Task).options(joinedload(Task.driver))
    if status is not None:
        query = query.where(Task.status == status)
    return [task_dict(task) for task in db.scalars(query.order_by(Task.id.desc()).offset(offset).limit(limit))]


@router.get("/available")
def available_tasks(offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200), driver: Driver = Depends(eligible_driver), db: Session = Depends(get_db)):
    return [task_dict(task) for task in db.scalars(select(Task).where(Task.status == TaskStatus.DISPONIVEL).order_by(Task.id.desc()).offset(offset).limit(limit))]


@router.get("/mine")
def my_tasks(completed: bool = False, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200), driver: Driver = Depends(eligible_driver), db: Session = Depends(get_db)):
    query = select(Task).options(joinedload(Task.driver)).where(Task.driver_id == driver.id)
    query = query.where(Task.status.in_([TaskStatus.CONCLUIDA, TaskStatus.CANCELADA])) if completed else query.where(Task.status.in_([TaskStatus.ACEITA, TaskStatus.EM_ANDAMENTO]))
    return [task_dict(task) for task in db.scalars(query.order_by(Task.id.desc()).offset(offset).limit(limit))]


@router.get("/{task_id}")
def task_detail(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    driver = eligible_driver(user, db) if user.role == UserRole.MOTORISTA else None
    task = find_task(db, task_id)
    if driver and task.status != TaskStatus.DISPONIVEL and task.driver_id != driver.id:
        raise HTTPException(403, "Esta tarefa pertence a outro motorista")
    return task_dict(task)


@router.get("/{task_id}/locations")
def task_locations(task_id: int, driver: Driver = Depends(eligible_driver), db: Session = Depends(get_db)):
    task = find_task(db, task_id)
    if task.status != TaskStatus.DISPONIVEL:
        raise HTTPException(409, "Esta tarefa já foi aceita ou cancelada")
    from app.services.trips import get_active_trip
    if get_active_trip(db, driver.id) is None:
        return {"required": False, "candidates": []}
    from app.services.geocoding_cache import geocode
    result = geocode(db, task.endereco)
    if not result.get('candidates') and result.get('errors'):
        limited = any(error.get('status') == 429 for error in result['errors'])
        raise HTTPException(429 if limited else 503,
                            'Consulta de endereços indisponível. Aguarde e tente novamente.')
    candidates = []
    for point in result.get('candidates', []):
        if not point.get('street_found') and not point.get('manual_confirmed'):
            continue
        token = jwt.encode({
            'purpose': 'task_location', 'task_id': task.id, 'driver_id': driver.id,
            'address': task.endereco, 'point': point,
            'exp': datetime.now(UTC) + timedelta(minutes=15),
        }, settings.secret_key, algorithm='HS256')
        candidates.append({**point, 'location_token': token})
    return {"required": True, "candidates": candidates}


@router.post("/{task_id}/accept")
def accept_task(task_id: int, body: TaskAcceptance | None = None, driver: Driver = Depends(eligible_driver), db: Session = Depends(get_db)):
    selected_point = None
    if body is not None:
        task = find_task(db, task_id)
        try:
            payload = jwt.decode(body.location_token, settings.secret_key, algorithms=['HS256'])
            if (payload.get('purpose') != 'task_location' or payload.get('task_id') != task.id
                    or payload.get('driver_id') != driver.id or payload.get('address') != task.endereco):
                raise InvalidTokenError()
            selected_point = payload['point']
        except (InvalidTokenError, KeyError):
            raise HTTPException(422, 'Seleção inválida ou expirada. Consulte os endereços novamente.') from None
    # The conditional UPDATE arbitrates competing requests inside the database.
    result = db.execute(update(Task).where(Task.id == task_id, Task.status == TaskStatus.DISPONIVEL, Task.driver_id.is_(None)).values(status=TaskStatus.ACEITA, driver_id=driver.id, accepted_at=utcnow()), execution_options={"synchronize_session": False})
    if result.rowcount != 1:
        db.rollback()
        find_task(db, task_id)
        raise HTTPException(409, "Esta tarefa já foi aceita. Escolha outra tarefa ou continue sua rota.")
    from app.services.task_routing import insert_task
    try:
        insert_task(db, find_task(db, task_id), driver, selected_point=selected_point)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.expire_all()
    return task_dict(find_task(db, task_id))


@router.post("/{task_id}/complete")
def complete_task(task_id: int, driver: Driver = Depends(eligible_driver), db: Session = Depends(get_db)):
    result = db.execute(update(Task).where(Task.id == task_id, Task.driver_id == driver.id, Task.status.in_([TaskStatus.ACEITA, TaskStatus.EM_ANDAMENTO])).values(status=TaskStatus.CONCLUIDA, completed_at=utcnow()), execution_options={"synchronize_session": False})
    if result.rowcount != 1:
        db.rollback()
        task = find_task(db, task_id)
        if task.driver_id != driver.id:
            raise HTTPException(403, "Você só pode concluir suas próprias tarefas")
        raise HTTPException(409, "Esta tarefa já foi concluída ou não pode ser concluída")
    from app.services.task_routing import resolve_task_stop
    resolve_task_stop(db, find_task(db, task_id))
    db.commit()
    db.expire_all()
    return task_dict(find_task(db, task_id))


@router.post("/{task_id}/cancel")
def cancel_task(task_id: int, user: User = Depends(require_operations), db: Session = Depends(get_db)):
    result = db.execute(update(Task).where(Task.id == task_id, Task.status.in_([TaskStatus.DISPONIVEL, TaskStatus.ACEITA, TaskStatus.EM_ANDAMENTO])).values(status=TaskStatus.CANCELADA), execution_options={"synchronize_session": False})
    if result.rowcount != 1:
        db.rollback()
        find_task(db, task_id)
        raise HTTPException(409, "Esta tarefa já foi concluída ou cancelada")
    from app.services.task_routing import resolve_task_stop
    resolve_task_stop(db, find_task(db, task_id), cancelled=True)
    db.commit()
    db.expire_all()
    return task_dict(find_task(db, task_id))
