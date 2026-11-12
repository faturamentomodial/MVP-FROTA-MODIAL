from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.entities import Driver, TimestampMixin


class TaskStatus(str, PyEnum):
    DISPONIVEL = "DISPONIVEL"
    ACEITA = "ACEITA"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    CONCLUIDA = "CONCLUIDA"
    CANCELADA = "CANCELADA"


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_driver_status", "driver_id", "status"),
        CheckConstraint("(status = 'CANCELADA' AND completed_at IS NULL) OR (status = 'DISPONIVEL' AND driver_id IS NULL AND accepted_at IS NULL AND started_at IS NULL AND completed_at IS NULL) OR (status IN ('ACEITA', 'EM_ANDAMENTO', 'CONCLUIDA') AND driver_id IS NOT NULL AND accepted_at IS NOT NULL AND ((status = 'CONCLUIDA' AND completed_at IS NOT NULL) OR (status != 'CONCLUIDA' AND completed_at IS NULL)))", name="ck_task_assignment"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    titulo: Mapped[str] = mapped_column(String(160), nullable=False)
    endereco: Mapped[str] = mapped_column(String(500), nullable=False)
    observacoes: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus, native_enum=False, create_constraint=True, name="task_status"), default=TaskStatus.DISPONIVEL, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    driver: Mapped[Driver | None] = relationship()
