from datetime import date, time
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal
from app.schemas.route_plans import Point, PlannedInvoice


class TemplateInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default='', max_length=2000)
    notes: str = Field(default='', max_length=4000)
    active: bool = True
    origin: Point | None = None
    return_point: Point | None = None
    profile: Literal['car', 'truck'] = 'truck'
    objective: Literal['duration', 'distance'] = 'duration'
    weekdays: list[int] = Field(default_factory=list, max_length=7)
    addresses: list[Point] = Field(default_factory=list, max_length=100)
    invoices: list[PlannedInvoice] = Field(default_factory=list, max_length=100)
    revision: int = Field(default=0, ge=0)

    @model_validator(mode='after')
    def validate_stops(self):
        if any(d not in range(7) for d in self.weekdays) or len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError('Dias habituais inválidos')
        if len({n.number for n in self.invoices}) != len(self.invoices):
            raise ValueError('Número de nota duplicado')
        if self.addresses and self.invoices:
            raise ValueError('Escolha paradas por endereços ou por notas fiscais')
        return self


class ExecutionInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    template_id: int = Field(gt=0)
    template_revision: int = Field(ge=0)
    date: date
    departure_time: time | None = None
    driver_id: int = Field(gt=0)
    vehicle_id: int = Field(gt=0)
    notes: str = Field(default='', max_length=4000)
    request_key: str = Field(min_length=8, max_length=80)
    revision: int = Field(default=0, ge=0)

    @model_validator(mode='after')
    def minute_precision(self):
        if self.departure_time and (self.departure_time.second or self.departure_time.microsecond or self.departure_time.tzinfo):
            raise ValueError('Informe horário local com precisão de minutos')
        return self
