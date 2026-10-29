from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator


class Point(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    address: str = Field(min_length=5, max_length=500)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)


class PlannedInvoice(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    number: str = Field(min_length=1, max_length=80)
    volumes: int = Field(gt=0, le=1000000)
    destination: Point
    source: Literal["MANUAL"] = "MANUAL"
    external_id: str | None = Field(default=None, max_length=120)


class PlanInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    vehicle_id: int | None = None
    driver_id: int | None = Field(default=None, gt=0)
    profile: Literal["car", "truck"] = "car"
    origin: Point | None = None
    invoices: list[PlannedInvoice] = Field(default_factory=list, max_length=10)
    objective: Literal["duration", "distance"] = "duration"
    revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def unique_numbers(self):
        if len({n.number for n in self.invoices}) != len(self.invoices):
            raise ValueError("Número de nota duplicado")
        return self


class CalculateInput(BaseModel):
    revision: int = Field(ge=0)
    optimize: bool = True


class RevisionInput(BaseModel):
    revision: int = Field(ge=0)
