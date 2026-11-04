from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.schemas.route_plans import Point, PlanInput, invoice_identity


class DistributionNote(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    id: str = Field(pattern=r'^[a-zA-Z0-9-]{1,36}$')
    number: str = Field(min_length=1, max_length=80)
    volumes: int = Field(gt=0, le=1000000)
    partner: str = Field(default='', max_length=240)
    company: str = Field(default='', max_length=80)
    series: str = Field(default='', max_length=80)
    source: Literal['MANUAL', 'SANKHYA'] = 'MANUAL'
    external_id: str | None = Field(default=None, max_length=120)
    address: str = Field(min_length=5, max_length=500)
    destination: Point | None = None
    geocode_status: Literal['PENDENTE', 'VALIDADO'] = 'PENDENTE'

    @model_validator(mode='after')
    def validate_location(self):
        if (self.destination is not None) != (self.geocode_status == 'VALIDADO'):
            raise ValueError('Confirme a localização para validar o endereço')
        if self.source == 'SANKHYA' and not self.external_id:
            raise ValueError('Nota Sankhya exige identificador interno')
        return self


class DistributionRouteInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    key: str = Field(pattern=r'^[a-zA-Z0-9-]{1,36}$')
    plan_id: int | None = None
    color: str = Field(pattern=r'^#[0-9a-fA-F]{6}$')
    plan: PlanInput
    invoice_ids: list[str] = Field(default_factory=list, max_length=10)


class DistributionInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=160)
    revision: int = Field(default=0, ge=0)
    notes: list[DistributionNote] = Field(default_factory=list, max_length=1000)
    routes: list[DistributionRouteInput] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def unique_assignments(self):
        ids = [n.id for n in self.notes]
        identities = [invoice_identity(n.model_dump()) for n in self.notes]
        if len(set(ids)) != len(ids) or len(set(identities)) != len(identities):
            raise ValueError('NF duplicada neste conjunto de distribuição')
        keys = [r.key for r in self.routes]
        plans = [r.plan_id for r in self.routes if r.plan_id is not None]
        assigned = [i for r in self.routes for i in r.invoice_ids]
        if len(set(keys)) != len(keys) or len(set(plans)) != len(plans):
            raise ValueError('Rota duplicada')
        if len(set(assigned)) != len(assigned):
            raise ValueError('Uma NF não pode pertencer a duas rotas')
        validated = {n.id for n in self.notes if n.destination}
        if not set(assigned).issubset(validated):
            raise ValueError('Somente notas com localização validada podem ser distribuídas')
        return self
