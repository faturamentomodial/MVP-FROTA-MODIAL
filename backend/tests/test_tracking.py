from datetime import UTC, datetime, timedelta

import pytest

from app.core.database import SessionLocal
from app.models.entities import TrackingPositionRecord
from app.services.tracking import PositronTrackingProvider, ProviderNotConfigured, TrackingPosition


def test_tracking_requires_admin(client, driver_headers):
    assert client.get('/api/tracking').status_code == 401
    assert client.get('/api/tracking', headers=driver_headers).status_code == 403
    assert client.put('/api/tracking/1/link', headers=driver_headers, json={'tracker_id':'123'}).status_code == 403
    assert client.get('/api/tracking/1/history', headers=driver_headers).status_code == 403


def test_links_and_empty_fleet(client, admin_headers):
    response = client.get('/api/tracking', headers=admin_headers).json()
    assert response['provider_ready'] is False
    assert response['items'][0]['status'] == 'SEM_VINCULO'
    assert response['items'][0]['position'] is None
    assert client.put('/api/tracking/1/link', headers=admin_headers, json={'tracker_id':'  X123  '}).status_code == 200
    assert client.get('/api/tracking', headers=admin_headers).json()['items'][0]['status'] == 'AGUARDANDO_POSICAO'
    assert client.put('/api/tracking/1/link', headers=admin_headers, json={'tracker_id':'   '}).status_code == 422
    assert client.put('/api/tracking/999/link', headers=admin_headers, json={'tracker_id':'X'}).status_code == 404
    created = client.post('/api/vehicles', headers=admin_headers, json={'placa':'DEF4G56','marca':'VW','modelo':'Delivery','tipo':'Bau','km_atual':0}).json()
    assert client.put(f"/api/tracking/{created['id']}/link", headers=admin_headers, json={'tracker_id':'X123'}).status_code == 409


def test_positions_history_and_reassignment(client, admin_headers):
    client.put('/api/tracking/1/link', headers=admin_headers, json={'tracker_id':'123'})
    now = datetime.now(UTC)
    with SessionLocal() as db:
        db.add_all([TrackingPositionRecord(vehicle_id=1, latitude=-23, longitude=-46, recorded_at=now-timedelta(minutes=10), speed=0),
                    TrackingPositionRecord(vehicle_id=1, latitude=-23.1, longitude=-46.1, recorded_at=now, speed=62)])
        db.commit()
    item = client.get('/api/tracking', headers=admin_headers).json()['items'][0]
    assert item['status'] == 'EM_MOVIMENTO'
    assert item['position']['speed'] == 62
    history = client.get('/api/tracking/1/history', headers=admin_headers).json()
    assert len(history) == 2
    assert history[0]['recorded_at'] < history[1]['recorded_at']
    client.put('/api/tracking/1/link', headers=admin_headers, json={'tracker_id':'456'})
    assert client.get('/api/tracking/1/history', headers=admin_headers).json() == []


def test_provider_explicitly_unavailable():
    with pytest.raises(ProviderNotConfigured):
        PositronTrackingProvider().positions()
    with pytest.raises(ValueError):
        TrackingPosition(tracker_id='1', latitude=91, longitude=0, recorded_at=datetime.now(UTC))


def test_tracking_migration_preserves_vehicle():
    from sqlalchemy import create_engine, text

    import importlib.util
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('tracking_migration', Path('migrations/versions/20261009_0007_tracking.py'))
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE vehicles (id INTEGER PRIMARY KEY, placa TEXT NOT NULL)'))
        connection.execute(text("INSERT INTO vehicles VALUES (1, 'ABC1D23')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert connection.scalar(text('SELECT placa FROM vehicles')) == 'ABC1D23'
            connection.execute(text("INSERT INTO vehicle_tracking VALUES (1, 'POSITRON', '123', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
            migration.downgrade()
            assert connection.scalar(text('SELECT placa FROM vehicles')) == 'ABC1D23'
    engine.dispose()
