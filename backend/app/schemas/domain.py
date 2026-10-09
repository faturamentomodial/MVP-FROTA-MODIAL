from datetime import UTC, datetime
from typing import Literal
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

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


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("*", mode="after")
    @classmethod
    def utc_dates(cls, value):
        # SQLite drops timezone metadata; all stored timestamps are UTC.
        if isinstance(value, datetime):
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return value


class LoginIn(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=6, max_length=128)


class UserOut(ORMModel):
    id: int
    nome: str
    email: EmailStr
    role: UserRole
    ativo: bool


class ActiveUpdate(BaseModel):
    ativo: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class DriverBase(BaseModel):
    nome: str = Field(min_length=2, max_length=160)
    cpf: str | None = None
    telefone: str | None = Field(default=None, min_length=8, max_length=20)
    email: EmailStr
    ativo: bool = True

    @field_validator("cpf")
    @classmethod
    def clean_cpf(cls, value: str | None) -> str | None:
        if value is None:
            return value
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) != 11:
            raise ValueError("CPF deve conter 11 dígitos")
        return digits


class DriverCreate(DriverBase):
    senha: str = Field(min_length=8, max_length=128)


class DriverUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=160)
    cpf: str | None = None
    telefone: str | None = Field(default=None, min_length=8, max_length=20)
    email: EmailStr | None = None
    senha: str | None = Field(default=None, min_length=8, max_length=128)
    ativo: bool | None = None

    @field_validator("cpf")
    @classmethod
    def clean_cpf(cls, value: str | None) -> str | None:
        if value is None:
            return value
        digits = "".join(ch for ch in value if ch.isdigit())
        if len(digits) != 11:
            raise ValueError("CPF deve conter 11 dígitos")
        return digits


class DriverOut(ORMModel):
    id: int
    nome: str
    cpf: str
    telefone: str
    user_id: int
    ativo: bool
    created_at: datetime
    updated_at: datetime
    email: EmailStr | None = None


class VehicleBase(BaseModel):
    placa: str = Field(min_length=7, max_length=8)
    marca: str = Field(min_length=1, max_length=80)
    modelo: str = Field(min_length=1, max_length=120)
    tipo: str = Field(min_length=1, max_length=80)
    km_atual: int = Field(ge=0)
    status: VehicleStatus = VehicleStatus.DISPONIVEL
    ativo: bool = True

    @field_validator("placa")
    @classmethod
    def clean_plate(cls, value: str) -> str:
        return value.replace("-", "").replace(" ", "").upper()


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    placa: str | None = Field(default=None, min_length=7, max_length=8)
    marca: str | None = Field(default=None, min_length=1, max_length=80)
    modelo: str | None = Field(default=None, min_length=1, max_length=120)
    tipo: str | None = Field(default=None, min_length=1, max_length=80)
    km_atual: int | None = Field(default=None, ge=0)
    status: VehicleStatus | None = None
    ativo: bool | None = None

    @field_validator("placa")
    @classmethod
    def clean_plate(cls, value: str | None) -> str | None:
        return value.replace("-", "").replace(" ", "").upper() if value else value


class VehicleOut(ORMModel):
    id: int
    placa: str
    marca: str
    modelo: str
    tipo: str
    km_atual: int
    status: VehicleStatus
    ativo: bool
    created_at: datetime
    updated_at: datetime


class TripCreate(BaseModel):
    vehicle_id: int
    km_inicial: int = Field(ge=0)


class TripFinish(BaseModel):
    km_final: int = Field(ge=0)
    observacao: str | None = Field(default=None, max_length=2000)


class TripInvoiceIn(BaseModel):
    numero_nota: str = Field(min_length=1, max_length=80)
    volumes: int = Field(ge=1, le=999999)

    @field_validator("numero_nota")
    @classmethod
    def clean_invoice_number(cls, value: str) -> str:
        return " ".join(value.strip().split())


class TripCargoUpdate(BaseModel):
    notas: list[TripInvoiceIn] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def prevent_duplicate_invoice_numbers(self):
        numbers = [item.numero_nota.casefold() for item in self.notas]
        if len(numbers) != len(set(numbers)):
            raise ValueError("Números de nota não podem ser repetidos")
        return self


class DeliveryOrderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invoice_ids: list[int] = Field(min_length=1, max_length=100)
    revision: int = Field(ge=0)


class DeliveryOccurrenceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    motivo: Literal["CLIENTE_FECHADO", "CLIENTE_RECUSOU", "CLIENTE_AUSENTE", "ENDERECO_NAO_LOCALIZADO", "MERCADORIA_RECUSADA", "OUTRO"]
    observacao: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def require_other_note(self):
        self.observacao = (self.observacao or "").strip() or None
        if self.motivo == "OUTRO" and not self.observacao:
            raise ValueError("Descreva o motivo da ocorrência")
        return self


class TripInvoiceOut(ORMModel):
    position: int
    id: int
    numero_nota: str
    volumes: int
    status: DeliveryStatus
    started_at: datetime | None
    delivered_at: datetime | None
    occurrence_at: datetime | None
    occurrence_reason: str | None
    occurrence_note: str | None


class TripOut(ORMModel):
    delivery_revision: int
    id: int
    driver_id: int
    vehicle_id: int
    data_saida: datetime
    km_inicial: int
    data_retorno: datetime | None
    km_final: int | None
    km_percorrido: int | None
    status: TripStatus
    observacao: str | None
    created_at: datetime
    updated_at: datetime
    driver_name: str | None = None
    vehicle_plate: str | None = None
    checklist_id: int | None = None
    occurrence_count: int = 0
    notas: list[TripInvoiceOut] = Field(default_factory=list)
    total_volumes: int = 0


class ChecklistItemCreate(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    descricao: str | None = Field(default=None, max_length=1000)
    obrigatorio: bool = True
    ativo: bool = True
    ordem: int = Field(default=0, ge=0)


class ChecklistItemUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=120)
    descricao: str | None = Field(default=None, max_length=1000)
    obrigatorio: bool | None = None
    ativo: bool | None = None
    ordem: int | None = Field(default=None, ge=0)


class ChecklistItemOut(ORMModel):
    id: int
    nome: str
    descricao: str | None
    ativo: bool
    ordem: int
    obrigatorio: bool


class ChecklistAnswerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checklist_item_id: int
    status: AnswerStatus
    observacao: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_problem_description(self):
        if self.status == AnswerStatus.PROBLEMA and not (self.observacao or "").strip():
            raise ValueError("Descreva o problema encontrado")
        return self


class ChecklistCreate(BaseModel):
    answers: list[ChecklistAnswerIn] = Field(min_length=1)
    observacao: str | None = Field(default=None, max_length=2000)


class ChecklistAnswerOut(ORMModel):
    id: int
    checklist_item_id: int
    status: AnswerStatus
    observacao: str | None
    created_at: datetime
    item: ChecklistItemOut


class ChecklistOut(ORMModel):
    id: int
    trip_id: int
    driver_id: int
    vehicle_id: int
    data_hora: datetime
    status: ChecklistStatus
    observacao: str | None
    created_at: datetime
    answers: list[ChecklistAnswerOut]


class OccurrenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trip_id: int
    tipo: OccurrenceType
    descricao: str = Field(min_length=3, max_length=4000)
    local: str | None = Field(default=None, max_length=255)


class OccurrenceUpdate(BaseModel):
    status: OccurrenceStatus | None = None
    observacao_gestor: str | None = Field(default=None, max_length=4000)


class OccurrenceOut(ORMModel):
    invoice_id: int | None = None
    id: int
    trip_id: int
    driver_id: int
    vehicle_id: int
    tipo: OccurrenceType
    descricao: str
    data_hora: datetime
    local: str | None
    status: OccurrenceStatus
    observacao_gestor: str | None
    created_at: datetime
    updated_at: datetime
    driver_name: str | None = None
    vehicle_plate: str | None = None


class DeliveryRouteSummary(ORMModel):
    id: int
    driver_name: str
    total: int
    delivered: int
    failed: int
    pending: int
    last_delivered_at: datetime | None


class DashboardOut(BaseModel):
    delivery_routes: list[DeliveryRouteSummary] = Field(default_factory=list)
    total_vehicles: int
    available_vehicles: int
    vehicles_in_trip: int
    vehicles_attention: int
    inactive_vehicles: int
    total_trips: int
    total_checklists: int
    checklists_today: int
    checklists_this_week: int
    checklists_this_month: int
    checklists_with_problems: int
    total_occurrences: int
    open_occurrences: int
    in_analysis_occurrences: int
    resolved_occurrences: int
    total_km: int
    checklist_series: list[dict]
    occurrence_by_type: list[dict]
    drivers: list[dict]
    vehicles: list[dict]


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int
