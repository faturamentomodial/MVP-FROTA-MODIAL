"""Rolling back application features must retain applied migration revisions."""
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from app.core.config import settings


def test_previous_application_accepts_distribution_revision(tmp_path, monkeypatch):
    database_url = f"sqlite:///{(tmp_path / 'rollback.db').as_posix()}"
    monkeypatch.setattr(settings, 'database_url', database_url)
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE alembic_version (version_num VARCHAR(32) PRIMARY KEY)'))
        connection.execute(text("INSERT INTO alembic_version VALUES ('20261104_0012')"))
        connection.execute(text('CREATE TABLE distributions (id INTEGER PRIMARY KEY, name VARCHAR(160))'))
        connection.execute(text("INSERT INTO distributions VALUES (1, 'Preservar dados')"))
    command.upgrade(Config('alembic.ini'), 'head')
    with engine.connect() as connection:
        assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar() == '20261104_0012'
        assert connection.execute(text('SELECT name FROM distributions WHERE id=1')).scalar() == 'Preservar dados'
    engine.dispose()
