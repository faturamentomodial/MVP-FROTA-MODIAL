from math import ceil

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


def paginate(db: Session, statement: Select, page: int, page_size: int) -> tuple[list, int, int]:
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    items = list(db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all())
    return items, total, ceil(total / page_size) if total else 0

