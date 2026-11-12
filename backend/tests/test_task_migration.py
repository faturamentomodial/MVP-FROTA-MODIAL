from pathlib import Path
from tempfile import TemporaryDirectory

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.core.config import settings


def test_tasks_upgrade_preserves_existing_records(monkeypatch):
    with TemporaryDirectory(prefix="tasks-migration-") as directory:
        url = f"sqlite+pysqlite:///{Path(directory).as_posix()}/tasks.db"
        monkeypatch.setattr(settings, 'database_url', url)
        config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
        config.set_main_option('script_location', str(Path(__file__).resolve().parents[1] / 'migrations'))
        command.upgrade(config, 'head')
        engine = create_engine(url)
        assert 'tasks' in inspect(engine).get_table_names()
        command.downgrade(config, '20261028_0008')
        with engine.begin() as db:
            db.execute(text("INSERT INTO users (id,nome,email,senha_hash,role,ativo,created_at,updated_at) VALUES (900,'Preservar','preservar@example.com','hash','ADMIN',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        command.upgrade(config, 'head')
        with engine.connect() as db:
            assert db.scalar(text('SELECT nome FROM users WHERE id=900')) == 'Preservar'
        indexes = {index['name'] for index in inspect(engine).get_indexes('tasks')}
        assert {'ix_tasks_status','ix_tasks_driver_status'} <= indexes
        assert len(inspect(engine).get_foreign_keys('tasks')) == 2
        engine.dispose()


def test_cancellation_upgrade_preserves_tasks(monkeypatch):
    with TemporaryDirectory(prefix='task-cancellation-') as directory:
        url = f"sqlite+pysqlite:///{Path(directory).as_posix()}/tasks.db"
        monkeypatch.setattr(settings, 'database_url', url)
        config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
        config.set_main_option('script_location', str(Path(__file__).resolve().parents[1] / 'migrations'))
        command.upgrade(config, 'head')
        command.downgrade(config, '20261110_0022')
        engine = create_engine(url)
        with engine.begin() as db:
            db.execute(text("INSERT INTO users (id,nome,email,senha_hash,role,ativo,created_at,updated_at) VALUES (900,'Operador','operador@example.com','hash','ADMIN',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
            db.execute(text("INSERT INTO tasks (id,titulo,endereco,observacoes,status,created_by,created_at,updated_at) VALUES (900,'Preservar','Rua Central','Coleta','DISPONIVEL',900,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        command.upgrade(config, 'head')
        with engine.begin() as db:
            assert db.scalar(text('SELECT titulo FROM tasks WHERE id=900')) == 'Preservar'
            db.execute(text("UPDATE tasks SET status='CANCELADA' WHERE id=900"))
            assert db.scalar(text('SELECT status FROM tasks WHERE id=900')) == 'CANCELADA'
        engine.dispose()
