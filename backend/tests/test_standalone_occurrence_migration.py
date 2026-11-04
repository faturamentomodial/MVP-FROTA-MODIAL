from pathlib import Path
from tempfile import TemporaryDirectory

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.core.config import settings


def test_upgrade_allows_occurrences_without_trip(monkeypatch):
    with TemporaryDirectory(prefix='occurrences-migration-') as directory:
        url = f'sqlite+pysqlite:///{Path(directory).as_posix()}/fleet.db'
        monkeypatch.setattr(settings, 'database_url', url)
        config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
        config.set_main_option('script_location', str(Path(__file__).resolve().parents[1] / 'migrations'))
        command.upgrade(config, 'head')
        command.downgrade(config, '20261103_0009')
        engine = create_engine(url)
        assert not next(c for c in inspect(engine).get_columns('occurrences') if c['name'] == 'trip_id')['nullable']
        with engine.begin() as db:
            db.execute(text("INSERT INTO users (id,nome,email,senha_hash,role,ativo,created_at,updated_at) VALUES (900,'Preservar','preservar@example.com','hash','ADMIN',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        command.upgrade(config, 'head')
        assert next(c for c in inspect(engine).get_columns('occurrences') if c['name'] == 'trip_id')['nullable']
        assert len(inspect(engine).get_foreign_keys('occurrences')) == 4
        with engine.connect() as db:
            assert db.scalar(text('SELECT nome FROM users WHERE id=900')) == 'Preservar'
        engine.dispose()
