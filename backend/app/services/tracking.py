"""Read-only Positron Sync integration (OpenAPI 1.0.10)."""
from abc import ABC, abstractmethod
from datetime import UTC, datetime
import json
from threading import RLock
from time import monotonic
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field, AwareDatetime
from app.core.config import settings


class TrackingPosition(BaseModel):
    tracker_id: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    recorded_at: AwareDatetime
    speed: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    address: str | None = None


class ProviderNotConfigured(RuntimeError):
    pass


class ProviderUnavailable(RuntimeError):
    pass


class TrackingProvider(ABC):
    @abstractmethod
    def positions(self) -> list[TrackingPosition]:
        """Fetch real positions using the provider's documented contract."""

    @abstractmethod
    def history(self, tracker_id: str, start: datetime, end: datetime) -> list[TrackingPosition]:
        """Fetch real historical positions."""


class PositronTrackingProvider(TrackingProvider):
    base_url = "https://webservices.positronrt.com.br/srb-external-ws"

    def __init__(self):
        self._token = None
        self._lock = RLock()

    @property
    def configured(self):
        return bool(settings.positron_login and settings.positron_password.get_secret_value())

    def _send(self, path, body=None, token=None):
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        with urlopen(Request(self.base_url + path, data=data, headers=headers), timeout=15) as response:
            return json.load(response)

    def _request(self, path, body=None):
        if not self.configured:
            raise ProviderNotConfigured("Configure as credenciais próprias da integração Pósitron no backend.")
        with self._lock:
            try:
                for attempt in range(2):
                    if self._token is None:
                        self._token = self._send("/api/v1/auth/token", {
                            "login": settings.positron_login,
                            "password": settings.positron_password.get_secret_value(),
                        })["token"]
                    try:
                        return self._send(path, body, self._token)
                    except HTTPError as exc:
                        if exc.code != 401 or attempt:
                            raise
                        self._token = None
            except (URLError, TimeoutError, OSError, ValueError, KeyError, TypeError) as exc:
                raise ProviderUnavailable("Não foi possível consultar a Pósitron. Verifique as credenciais e a disponibilidade do serviço.") from exc

    @staticmethod
    def _normalize(rows):
        positions = []
        try:
            if not isinstance(rows, list):
                raise ValueError("Expected list")
            for row in rows:
                if row.get("gps") is False or row.get("estimated") is True:
                    continue
                # API dates without an offset use UTC, per the provider contract.
                date = datetime.fromisoformat(row["moduleDatetime"].replace("Z", "+00:00"))
                positions.append(TrackingPosition(
                    tracker_id=str(row["idVehicle"]), latitude=row["latitude"],
                    longitude=row["longitude"], recorded_at=date.replace(tzinfo=UTC) if date.tzinfo is None else date,
                    speed=row.get("speed"), address=row.get("relationalAddress"),
                ))
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            raise ProviderUnavailable("A Pósitron retornou posições em formato inválido.") from exc
        return positions

    def positions(self) -> list[TrackingPosition]:
        return self._normalize(self._request("/api/v1/position/latest?withAddress=true"))

    def vehicles(self):
        return self._request("/api/v1/vehicle/list")

    def history(self, tracker_id: str, start: datetime, end: datetime) -> list[TrackingPosition]:
        return self._normalize(self._request("/api/v1/position/history", {
            # The live API rejects fractional seconds with HTTP 400.
            "idVehicle": int(tracker_id), "start": start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": end.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), "withDetailedAddress": True,
        }))


provider = PositronTrackingProvider()
sync_lock = RLock()
last_sync = 0.0


def persist_positions(db, positions, links):
    from sqlalchemy import select
    from app.models.entities import TrackingPositionRecord

    count = 0
    for position in positions:
        link = links.get(position.tracker_id)
        if link is None or not link.active:
            continue
        existing = db.scalar(select(TrackingPositionRecord.id).where(
            TrackingPositionRecord.vehicle_id == link.vehicle_id,
            TrackingPositionRecord.recorded_at == position.recorded_at,
        ))
        if existing is None:
            db.add(TrackingPositionRecord(vehicle_id=link.vehicle_id,
                **position.model_dump(exclude={"tracker_id"})))
            db.flush()
            count += 1
    db.commit()
    return count


def sync_latest(db):
    from sqlalchemy import select
    from app.models.entities import VehicleTracking
    global last_sync
    with sync_lock:
        if monotonic() - last_sync < 30:
            return
        links = {link.tracker_id: link for link in db.scalars(select(VehicleTracking).where(VehicleTracking.active.is_(True)))}
        if links:
            persist_positions(db, provider.positions(), links)
        last_sync = monotonic()
