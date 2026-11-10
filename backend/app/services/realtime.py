"""Transactional module versions; one bounded database read per worker, not per client."""
import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from uuid import uuid4

from sqlalchemy import String, event, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.database import Base, SessionLocal

logger = logging.getLogger(__name__)

TABLE_TOPICS = {
    'users': 'users', 'drivers': 'drivers', 'vehicles': 'vehicles',
    'trips': 'trips', 'trip_invoices': 'trips',
    'checklist_items': 'checklists', 'checklists': 'checklists', 'checklist_answers': 'checklists',
    'occurrences': 'occurrences', 'tasks': 'tasks', 'pickups': 'pickups',
    'route_plans': 'routes', 'route_plan_versions': 'routes',
    'route_templates': 'routes', 'route_executions': 'routes',
    'vehicle_tracking': 'tracking', 'tracking_positions': 'tracking',
    'geocoded_addresses': 'pickups',
}
ALL_TOPICS = frozenset(TABLE_TOPICS.values())


class RealtimeVersion(Base):
    __tablename__ = 'realtime_versions'
    topic: Mapped[str] = mapped_column(String(32), primary_key=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)


def bump_versions(connection, topics):
    # Versions live in the SAME transaction: rollback never publishes an event.
    if connection.dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    for topic in sorted(topics):
        version = uuid4().hex
        statement = insert(RealtimeVersion.__table__).values(topic=topic, version=version)
        connection.execute(statement.on_conflict_do_update(
            index_elements=['topic'], set_={'version': version}))


@event.listens_for(Session, 'before_flush')
def track_flush(session, *_):
    topics = {
        TABLE_TOPICS[obj.__table__.name]
        for obj in session.new.union(session.dirty).union(session.deleted)
        if obj.__table__.name in TABLE_TOPICS
        and (obj in session.new or obj in session.deleted or session.is_modified(obj, include_collections=False))
    }
    if topics:
        bump_versions(session.connection(), topics)


@event.listens_for(Session, 'do_orm_execute')
def track_bulk(execute_state):
    if execute_state.is_update or execute_state.is_delete or execute_state.is_insert:
        table = getattr(execute_state.statement, 'table', None)
        topic = TABLE_TOPICS.get(getattr(table, 'name', None))
        if topic:
            bump_versions(execute_state.session.connection(), {topic})


def read_snapshot():
    from app.models import User
    with SessionLocal() as db:
        versions = dict(db.execute(select(RealtimeVersion.topic, RealtimeVersion.version)).all())
        users = {id: (role.value, active) for id, role, active in db.execute(select(User.id, User.role, User.ativo))}
        return versions, users


def allowed_topics(role):
    if role in ('ADMIN', 'MASTER'):
        return ALL_TOPICS
    if role == 'COMPRAS':
        return frozenset({'tasks', 'routes', 'trips', 'tracking', 'pickups', 'occurrences', 'checklists', 'users'})
    return frozenset({'tasks', 'routes', 'trips', 'vehicles', 'checklists', 'occurrences', 'users'})


class RealtimeHub:
    def __init__(self):
        self.versions = {}
        self.users = {}
        self.subscribers: set[asyncio.Queue] = set()

    async def watch(self):
        while True:
            try:
                # No database polling while there are no connected clients.
                if self.subscribers:
                    versions, users = await asyncio.to_thread(read_snapshot)
                    if versions != self.versions or users != self.users:
                        self.versions, self.users = versions, users
                        for queue in tuple(self.subscribers):
                            if queue.full():
                                queue.get_nowait()
                            queue.put_nowait((versions, users))
            except Exception:
                logger.exception('Realtime snapshot failed; retrying')
            await asyncio.sleep(1)


@asynccontextmanager
async def realtime_lifespan(app):
    hub = RealtimeHub()
    app.state.realtime = hub
    task = asyncio.create_task(hub.watch())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
