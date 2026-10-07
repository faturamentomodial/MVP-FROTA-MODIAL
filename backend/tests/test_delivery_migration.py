from pathlib import Path
from datetime import UTC, datetime
from tempfile import TemporaryDirectory

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.core.config import settings


def test_fresh_install_and_legacy_migration_preserve_data(monkeypatch):
    with TemporaryDirectory(prefix="fleet-migration-") as directory:
        verify_migration(Path(directory), monkeypatch)


def verify_migration(tmp_path, monkeypatch):
    database = tmp_path / "migration.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+pysqlite:///{database.as_posix()}")
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    command.upgrade(config, "head")
    engine = create_engine(settings.database_url)
    assert "status" in {c["name"] for c in inspect(engine).get_columns("trip_invoices")}
    assert "invoice_id" in {c["name"] for c in inspect(engine).get_columns("occurrences")}
    # Recreate the pre-delivery schema; stamp and upgrade it with legacy data.
    command.downgrade(config, "20260922_0002")
    now = datetime.now(UTC).isoformat()
    with engine.begin() as db:
        db.execute(text("INSERT INTO trip_invoices (id,trip_id,numero_nota,volumes,created_at) VALUES (1,42,'LEGACY-1',3,:now)"), {"now":now})
    command.upgrade(config, "head")
    with engine.connect() as db:
        row = db.execute(text("SELECT numero_nota,volumes,status,started_at,delivered_at FROM trip_invoices WHERE id=1")).one()
        assert tuple(row) == ("LEGACY-1",3,"PENDENTE",None,None)
        assert db.scalar(text("SELECT position FROM trip_invoices WHERE id=1")) == 1
    fk = inspect(engine).get_foreign_keys("occurrences")
    assert any(k["constrained_columns"] == ["invoice_id"] for k in fk)
    unique = inspect(engine).get_unique_constraints("occurrences")
    assert any(k["column_names"] == ["invoice_id"] for k in unique)
    engine.dispose()
