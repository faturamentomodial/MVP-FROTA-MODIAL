import importlib.util
from pathlib import Path

from sqlalchemy import create_engine, text


def test_default_checklist_initialization_preserves_configuration(monkeypatch):
    path = Path(__file__).resolve().parents[1] / "migrations/versions/20261009_0006_default_checklist.py"
    spec = importlib.util.spec_from_file_location("checklist_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as db:
        db.execute(text("CREATE TABLE checklist_items (id INTEGER PRIMARY KEY, nome TEXT UNIQUE NOT NULL, ordem INTEGER NOT NULL, ativo BOOLEAN NOT NULL, obrigatorio BOOLEAN NOT NULL)"))
        monkeypatch.setattr(migration.op, "get_bind", lambda: db)
        migration.upgrade()
        assert db.scalar(text("SELECT COUNT(*) FROM checklist_items WHERE ativo=1 AND obrigatorio=1")) == 15
        migration.upgrade()
        assert db.scalar(text("SELECT COUNT(*) FROM checklist_items")) == 15
        db.execute(text("DELETE FROM checklist_items"))
        db.execute(text("INSERT INTO checklist_items VALUES (1, 'Customizado', 7, 0, 0)"))
        migration.upgrade()
        assert db.execute(text("SELECT nome, ordem, ativo, obrigatorio FROM checklist_items")).one() == ("Customizado", 7, 0, 0)
    engine.dispose()
