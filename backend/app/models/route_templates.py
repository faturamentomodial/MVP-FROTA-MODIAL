"""Reusable routes and independent, immutable operational snapshots."""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.entities import TimestampMixin


class RouteTemplate(TimestampMixin, Base):
    __tablename__ = 'route_templates'
    id: Mapped[int] = mapped_column(primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)


class RouteExecution(TimestampMixin, Base):
    __tablename__ = 'route_executions'
    __table_args__ = (CheckConstraint('ends_at > starts_at', name='ck_execution_interval'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey('route_templates.id'), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey('route_plans.id'), unique=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey('drivers.id'), index=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey('vehicles.id'), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    departure_time: Mapped[str | None] = mapped_column(String(5))
    notes: Mapped[str] = mapped_column(String(4000), default='')
    status: Mapped[str] = mapped_column(String(20), default='PROGRAMADA', nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    request_key: Mapped[str] = mapped_column(String(80), unique=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
