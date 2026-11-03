from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import get_current_user, require_admin, require_driver
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
def create_task(body: TaskCreate, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    task = Task(**body.model_dump(), created_by=user.id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task_dict(task)


@router.get("")
def admin_tasks(status: TaskStatus | None = None, offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200), user: User = Depends(require_admin), db: Session = Depends(get_db)):
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
    query = query.where(Task.status == TaskStatus.CONCLUIDA) if completed else query.where(Task.status.in_([TaskStatus.ACEITA, TaskStatus.EM_ANDAMENTO]))
    return [task_dict(task) for task in db.scalars(query.order_by(Task.id.desc()).offset(offset).limit(limit))]


@router.get("/{task_id}")
def task_detail(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    driver = eligible_driver(user, db) if user.role != UserRole.ADMIN else None
    task = find_task(db, task_id)
    if driver and task.status != TaskStatus.DISPONIVEL and task.driver_id != driver.id:
        raise HTTPException(403, "Esta tarefa pertence a outro motorista")
    return task_dict(task)


@router.post("/{task_id}/accept")
def accept_task(task_id: int, driver: Driver = Depends(eligible_driver), db: Session = Depends(get_db)):
    # The conditional UPDATE arbitrates competing requests inside the database.
    result = db.execute(update(Task).where(Task.id == task_id, Task.status == TaskStatus.DISPONIVEL, Task.driver_id.is_(None)).values(status=TaskStatus.ACEITA, driver_id=driver.id, accepted_at=utcnow()), execution_options={"synchronize_session": False})
    if result.rowcount != 1:
        db.rollback()
        find_task(db, task_id)
        raise HTTPException(409, "Esta tarefa já foi aceita. Escolha outra tarefa ou continue sua rota.")
    db.commit()
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
    db.commit()
    db.expire_all()
    return task_dict(find_task(db, task_id))
