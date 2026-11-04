from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.entities import TimestampMixin


class Pickup(TimestampMixin, Base):
    __tablename__ = "pickups"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(160), nullable=False)
    telefone: Mapped[str] = mapped_column(String(40), nullable=False)
    endereco: Mapped[str] = mapped_column(String(500), nullable=False)
