from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
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
