from functools import lru_cache
import logging
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env", BASE_DIR / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Modial Controle de Frota"
    environment: str = "development"
    secret_key: str = Field(default="change-me-in-production-with-at-least-32-characters")
    access_token_expire_minutes: int = 480
    database_url: str = "postgresql+psycopg://fleet:fleet@db:5432/fleet"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    frontend_dist: Path | None = None
    routes_geocoder_provider: Literal['geoapify', 'photon', 'nominatim'] = 'geoapify'
    routes_router_provider: Literal['geoapify', 'osrm'] = 'geoapify'
    geoapify_api_key: SecretStr = SecretStr('')
    routes_geocoder_url: str = 'https://nominatim.openstreetmap.org'
    routes_router_url: str = ''
    routes_timeout_seconds: float = Field(default=15, gt=0, le=60)
    routes_min_interval_seconds: float = Field(default=1, ge=0, le=60)
    geocoding_conflict_meters: float = Field(default=200, gt=0)
    geocoding_cache_seconds: int = Field(default=2592000, gt=0)
    geocoding_failure_cache_seconds: int = Field(default=300, gt=0)
    geocoding_primary_enabled: bool = True
    geocoding_require_neighborhood_match: bool = True
    sankhya_base_url: str = "https://api.sankhya.com.br"
    sankhya_client_id: str = ""
    sankhya_client_secret: SecretStr = SecretStr("")
    sankhya_token: SecretStr = SecretStr("")
    sankhya_timeout_seconds: float = Field(default=20, gt=0, le=60)
    positron_login: str = ""
    positron_password: SecretStr = SecretStr("")

    @model_validator(mode="after")
    def align_public_geocoder_url(self) -> "Settings":
        public_hosts = {
            "photon": "photon.komoot.io",
            "nominatim": "nominatim.openstreetmap.org",
        }
        host = urlsplit(self.routes_geocoder_url).hostname
        expected_host = public_hosts.get(self.routes_geocoder_provider)
        if expected_host is None:
            return self
        if host in public_hosts.values() and host != expected_host:
            self.routes_geocoder_url = f"https://{expected_host}"
            logging.getLogger(__name__).warning(
                "Geocoder URL incompatible with provider %s; using %s",
                self.routes_geocoder_provider, self.routes_geocoder_url,
            )
        return self

    @field_validator("database_url", mode="before")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        # Aceita URLs PostgreSQL de provedores sem o nome do driver SQLAlchemy.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
