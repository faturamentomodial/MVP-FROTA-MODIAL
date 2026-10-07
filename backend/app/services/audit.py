from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def audit(
    db: Session,
    user: User | None,
    action: str,
    entity: str,
    entity_id: int | None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            acao=action,
            entidade=entity,
            entidade_id=entity_id,
            detalhes=details,
        )
    )

