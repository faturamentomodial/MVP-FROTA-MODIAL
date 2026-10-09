"""Provider boundary: no vendor endpoints or credentials until a real contract exists."""
from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, Field, AwareDatetime


class TrackingPosition(BaseModel):
    tracker_id: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    recorded_at: AwareDatetime
    speed: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    address: str | None = None


class ProviderNotConfigured(RuntimeError):
    pass


class TrackingProvider(ABC):
    @abstractmethod
    def positions(self) -> list[TrackingPosition]:
        """Fetch real positions using the provider's documented contract."""

    @abstractmethod
    def history(self, tracker_id: str, start: datetime, end: datetime) -> list[TrackingPosition]:
        """Fetch real historical positions."""


class PositronTrackingProvider(TrackingProvider):
    def positions(self) -> list[TrackingPosition]:
        raise ProviderNotConfigured("Integração Pósitron pendente de documentação e credenciais do contrato.")

    def history(self, tracker_id: str, start: datetime, end: datetime) -> list[TrackingPosition]:
        raise ProviderNotConfigured("Integração Pósitron pendente de documentação e credenciais do contrato.")
