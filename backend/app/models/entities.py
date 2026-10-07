from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import (
    DeliveryStatus,
    AnswerStatus,
    ChecklistStatus,
    OccurrenceStatus,
    OccurrenceType,
    TripStatus,
    UserRole,
    VehicleStatus,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, native_enum=False), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    driver: Mapped["Driver | None"] = relationship(back_populates="user", uselist=False)


class Driver(TimestampMixin, Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    cpf: Mapped[str] = mapped_column(String(11), unique=True, nullable=False)
    telefone: Mapped[str] = mapped_column(String(20), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped[User] = relationship(back_populates="driver")
    trips: Mapped[list["Trip"]] = relationship(back_populates="driver")


class Vehicle(TimestampMixin, Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    placa: Mapped[str] = mapped_column(String(8), unique=True, index=True, nullable=False)
    marca: Mapped[str] = mapped_column(String(80), nullable=False)
    modelo: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo: Mapped[str] = mapped_column(String(80), nullable=False)
    km_atual: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[VehicleStatus] = mapped_column(Enum(VehicleStatus, native_enum=False), default=VehicleStatus.DISPONIVEL, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    trips: Mapped[list["Trip"]] = relationship(back_populates="vehicle")


class Trip(TimestampMixin, Base):
    __tablename__ = "trips"
    __table_args__ = (
        CheckConstraint("km_final IS NULL OR km_final >= km_inicial", name="ck_trip_final_km"),
        Index(
            "uq_open_trip_driver",
            "driver_id",
            unique=True,
            postgresql_where=text("status IN ('ABERTA', 'EM_ANDAMENTO')"),
            sqlite_where=text("status IN ('ABERTA', 'EM_ANDAMENTO')"),
        ),
        Index(
            "uq_open_trip_vehicle",
            "vehicle_id",
            unique=True,
            postgresql_where=text("status IN ('ABERTA', 'EM_ANDAMENTO')"),
            sqlite_where=text("status IN ('ABERTA', 'EM_ANDAMENTO')"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True, nullable=False)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True, nullable=False)
    data_saida: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    km_inicial: Mapped[int] = mapped_column(Integer, nullable=False)
    data_retorno: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    km_final: Mapped[int | None] = mapped_column(Integer)
    km_percorrido: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[TripStatus] = mapped_column(Enum(TripStatus, native_enum=False), default=TripStatus.ABERTA, index=True, nullable=False)
    observacao: Mapped[str | None] = mapped_column(Text)

    delivery_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    driver: Mapped[Driver] = relationship(back_populates="trips")
    vehicle: Mapped[Vehicle] = relationship(back_populates="trips")
    checklist: Mapped["Checklist | None"] = relationship(back_populates="trip", uselist=False, cascade="all, delete-orphan")
    invoices: Mapped[list["TripInvoice"]] = relationship(
        back_populates="trip", cascade="all, delete-orphan", lazy="selectin", order_by="(TripInvoice.position, TripInvoice.id)"
    )
    occurrences: Mapped[list["Occurrence"]] = relationship(back_populates="trip", cascade="all, delete-orphan")


class TripInvoice(Base):
    __tablename__ = "trip_invoices"
    __table_args__ = (
        CheckConstraint("volumes > 0", name="ck_trip_invoice_positive_volumes"),
        Index("ix_trip_invoice_position", "trip_id", "position"),
        UniqueConstraint("trip_id", "numero_nota", name="uq_trip_invoice_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), index=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    numero_nota: Mapped[str] = mapped_column(String(80), nullable=False)
    volumes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    status: Mapped[DeliveryStatus] = mapped_column(Enum(DeliveryStatus, native_enum=False, length=20), default=DeliveryStatus.PENDENTE, server_default="PENDENTE", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    occurrence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    occurrence_reason: Mapped[str | None] = mapped_column(String(80))
    occurrence_note: Mapped[str | None] = mapped_column(Text)

    trip: Mapped[Trip] = relationship(back_populates="invoices")


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ordem: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    obrigatorio: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Checklist(Base):
    __tablename__ = "checklists"

    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), unique=True, nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True, nullable=False)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True, nullable=False)
    data_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    status: Mapped[ChecklistStatus] = mapped_column(Enum(ChecklistStatus, native_enum=False), nullable=False)
    observacao: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    trip: Mapped[Trip] = relationship(back_populates="checklist")
    answers: Mapped[list["ChecklistAnswer"]] = relationship(back_populates="checklist", cascade="all, delete-orphan", lazy="selectin")


class ChecklistAnswer(Base):
    __tablename__ = "checklist_answers"
    __table_args__ = (UniqueConstraint("checklist_id", "checklist_item_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    checklist_id: Mapped[int] = mapped_column(ForeignKey("checklists.id"), nullable=False)
    checklist_item_id: Mapped[int] = mapped_column(ForeignKey("checklist_items.id"), nullable=False)
    status: Mapped[AnswerStatus] = mapped_column(Enum(AnswerStatus, native_enum=False), nullable=False)
    observacao: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    checklist: Mapped[Checklist] = relationship(back_populates="answers")
    item: Mapped[ChecklistItem] = relationship()


class Occurrence(TimestampMixin, Base):
    __tablename__ = "occurrences"

    __table_args__ = (UniqueConstraint("invoice_id", name="uq_occurrence_invoice"),)

    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("trip_invoices.id", name="fk_occurrence_invoice"))


    id: Mapped[int] = mapped_column(primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"), index=True, nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True, nullable=False)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), index=True, nullable=False)
    tipo: Mapped[OccurrenceType] = mapped_column(Enum(OccurrenceType, native_enum=False), index=True, nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    data_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    local: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[OccurrenceStatus] = mapped_column(Enum(OccurrenceStatus, native_enum=False), default=OccurrenceStatus.ABERTA, index=True, nullable=False)
    observacao_gestor: Mapped[str | None] = mapped_column(Text)

    trip: Mapped[Trip] = relationship(back_populates="occurrences")
    driver: Mapped[Driver] = relationship()
    vehicle: Mapped[Vehicle] = relationship()


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    acao: Mapped[str] = mapped_column(String(80), nullable=False)
    entidade: Mapped[str] = mapped_column(String(80), nullable=False)
    entidade_id: Mapped[int | None] = mapped_column(Integer)
    detalhes: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
