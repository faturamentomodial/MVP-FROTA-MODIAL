from pathlib import Path
from tempfile import TemporaryDirectory

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.core.config import settings


def test_deletion_migration_preserves_items(monkeypatch):
    with TemporaryDirectory(prefix='checklist-delete-') as directory:
        url = f'sqlite+pysqlite:///{Path(directory).as_posix()}/fleet.db'
        monkeypatch.setattr(settings, 'database_url', url)
        config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
        config.set_main_option('script_location', str(Path(__file__).resolve().parents[1] / 'migrations'))
        command.upgrade(config, 'head')
        command.downgrade(config, '20261104_0010')
        engine = create_engine(url)
        with engine.connect() as db:
            count = db.scalar(text('SELECT count(*) FROM checklist_items'))
        command.upgrade(config, 'head')
        assert 'excluido' in {c['name'] for c in inspect(engine).get_columns('checklist_items')}
        with engine.connect() as db:
            assert db.scalar(text('SELECT count(*) FROM checklist_items WHERE excluido = 0')) == count
        engine.dispose()
