from sqlalchemy import Boolean, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.entities import TimestampMixin


class Pickup(TimestampMixin, Base):
    __tablename__ = "pickups"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    telefone: Mapped[str] = mapped_column(String(40), nullable=False)
    endereco: Mapped[str] = mapped_column(String(500), nullable=False)

    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)

    tipo: Mapped[str | None] = mapped_column(String(20), nullable=True)
