from sqlalchemy import JSON, String, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.entities import TimestampMixin


class GeocodedAddress(TimestampMixin, Base):
    __tablename__ = 'geocoded_addresses'
    address: Mapped[str] = mapped_column(String(500), primary_key=True)
    result: Mapped[dict] = mapped_column(JSON, nullable=False)


class GeocodingQuota(Base):
    """Atomic reservations shared by every worker using the application database."""
    __tablename__ = 'geocoding_quotas'
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    available_at: Mapped[float] = mapped_column(Float, nullable=False)
