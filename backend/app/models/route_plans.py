"""Planning is independent of operational trips and invoices."""
from sqlalchemy import ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from app.models.entities import TimestampMixin


class RoutePlan(TimestampMixin, Base):
    __tablename__ = "route_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="RASCUNHO", nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)


class RoutePlanVersion(TimestampMixin, Base):
    __tablename__ = "route_plan_versions"
    __table_args__ = (UniqueConstraint("plan_id", "revision", name="uq_route_plan_revision"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("route_plans.id"), nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)


class Distribution(TimestampMixin, Base):
    __tablename__ = "distributions"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)


class DistributionVersion(TimestampMixin, Base):
    __tablename__ = "distribution_versions"
    __table_args__ = (UniqueConstraint("distribution_id", "revision", name="uq_distribution_revision"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    distribution_id: Mapped[int] = mapped_column(ForeignKey("distributions.id"), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)


class DistributionRoute(Base):
    __tablename__ = "distribution_routes"
    plan_id: Mapped[int] = mapped_column(ForeignKey("route_plans.id"), primary_key=True)
    distribution_id: Mapped[int] = mapped_column(ForeignKey("distributions.id"), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(36), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)
