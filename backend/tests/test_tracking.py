from datetime import UTC, datetime, timedelta

import pytest

from app.core.database import SessionLocal
from app.models.entities import TrackingPositionRecord
from app.services.tracking import PositronTrackingProvider, ProviderNotConfigured, TrackingPosition


@pytest.fixture(autouse=True)
def isolate_tracking_credentials(monkeypatch):
    from app.core.config import settings
    from pydantic import SecretStr
    import app.services.tracking as tracking
    monkeypatch.setattr(settings, 'positron_login', '')
    monkeypatch.setattr(settings, 'positron_password', SecretStr(''))
    monkeypatch.setattr(tracking.provider, '_token', None)
    monkeypatch.setattr(tracking, 'last_sync', 0)


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


def test_positron_auth_renewal_and_normalization(monkeypatch):
    from pydantic import SecretStr
    from urllib.error import HTTPError
    from app.core.config import settings
    monkeypatch.setattr(settings, 'positron_login', 'test')
    monkeypatch.setattr(settings, 'positron_password', SecretStr('secret'))
    provider = PositronTrackingProvider()
    calls = []

    def send(path, body=None, token=None):
        calls.append((path, body, token))
        if path.endswith('/token'):
            return {'token': f'token{len(calls)}'}
        if len(calls) == 2:
            raise HTTPError(path, 401, 'expired', {}, None)
        return [{'idVehicle': 123, 'moduleDatetime': '2026-10-14T13:00:00',
                 'latitude': -23, 'longitude': -46, 'speed': 35, 'gps': True}]

    monkeypatch.setattr(provider, '_send', send)
    result = provider.positions()
    assert len(calls) == 4
    assert calls[0][1] == {'login': 'test', 'password': 'secret'}
    assert result[0].tracker_id == '123'
    assert result[0].recorded_at == datetime(2026, 10, 14, 13, tzinfo=UTC)
    assert result[0].speed == 35


def test_history_dates_match_live_api_contract(monkeypatch):
    from datetime import timezone
    provider = PositronTrackingProvider()
    calls = []
    monkeypatch.setattr(provider, '_request', lambda path, body: calls.append((path, body)) or [])
    start = datetime(2026, 10, 22, 10, 30, 15, 123456, tzinfo=timezone(timedelta(hours=-3)))
    assert provider.history('123', start, start + timedelta(hours=1)) == []
    assert calls == [('/api/v1/position/history', {
        'idVehicle': 123, 'start': '2026-10-22T13:30:15Z',
        'end': '2026-10-22T14:30:15Z', 'withDetailedAddress': True,
    })]


def test_configure_tracking_matches_plate_and_is_idempotent():
    from app.configure_tracking import configure
    from app.models.entities import VehicleTracking
    from sqlalchemy import select, func
    point = TrackingPosition(tracker_id='123', latitude=-23, longitude=-46,
                             recorded_at=datetime.now(UTC))
    with SessionLocal() as db:
        result = configure(db, [{'id': 123, 'licensePlate': 'abc-1d23'}], [point])
        assert result['links_created'] == result['positions_stored'] == 1
        assert db.get(VehicleTracking, 1).tracker_id == '123'
        again = configure(db, [{'id': 999, 'licensePlate': 'ABC1D23'}], [point])
        assert again['links_created'] == again['positions_stored'] == 0
        assert db.get(VehicleTracking, 1).tracker_id == '123'
        assert db.scalar(select(func.count()).select_from(TrackingPositionRecord)) == 1


def test_configure_tracking_skips_ambiguous_and_unmatched_plates():
    from app.configure_tracking import configure
    with SessionLocal() as db:
        for rows in ([{'id': 123, 'licensePlate': 'OTHER'}],
                     [{'id': 123, 'licensePlate': 'ABC1D23'}, {'id': 456, 'licensePlate': 'ABC1D23'}]):
            result = configure(db, rows, [])
            assert result['links_created'] == result['active_links'] == 0
            assert result['unmatched_plates'] == ['ABC1D23']


def test_sync_and_remote_history(client, admin_headers, monkeypatch):
    import app.services.tracking as tracking
    from app.core.config import settings
    from pydantic import SecretStr
    monkeypatch.setattr(settings, 'positron_login', 'test')
    monkeypatch.setattr(settings, 'positron_password', SecretStr('secret'))
    monkeypatch.setattr(tracking, 'last_sync', 0)
    point = TrackingPosition(tracker_id='123', latitude=-23, longitude=-46, recorded_at=datetime.now(UTC), speed=30)
    monkeypatch.setattr(tracking.provider, 'positions', lambda: [point])
    monkeypatch.setattr(tracking.provider, 'history', lambda *args: [point, point])
    client.put('/api/tracking/1/link', headers=admin_headers, json={'tracker_id': '123'})
    fleet = client.get('/api/tracking', headers=admin_headers).json()
    assert fleet['provider_ready'] is True
    assert fleet['items'][0]['position']['speed'] == 30
    assert len(client.get('/api/tracking/1/history', headers=admin_headers).json()) == 1
    with SessionLocal() as db:
        from sqlalchemy import func, select
        assert db.scalar(select(func.count()).select_from(TrackingPositionRecord)) == 1

    def fail():
        raise tracking.ProviderUnavailable('Serviço indisponível')

    monkeypatch.setattr(tracking, 'last_sync', 0)
    monkeypatch.setattr(tracking.provider, 'positions', fail)
    fleet = client.get('/api/tracking', headers=admin_headers).json()
    assert fleet['provider_ready'] is False
    assert fleet['items'][0]['position']['speed'] == 30


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
