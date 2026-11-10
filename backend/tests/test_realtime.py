"""Independent WebSocket sessions represent users, tabs, and remote devices."""
from datetime import UTC, datetime, timedelta
import subprocess
import sys

import jwt
import pytest
from sqlalchemy import delete, update
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models import User, Vehicle
from app.models.enums import UserRole
from app.services.realtime import RealtimeVersion, allowed_topics, read_snapshot


def connect(client, headers):
    return client.websocket_connect('/api/realtime')


def authenticate(socket, headers):
    socket.send_json({'token': headers['Authorization'].split(' ', 1)[1]})
    message = socket.receive_json()
    assert message['type'] == 'sync'
    return message


def invalidation(socket, topic):
    # A snapshot can include a change committed during the initial handshake.
    for _ in range(5):
        message = socket.receive_json()
        if message['type'] == 'invalidate' and topic in message['topics']:
            assert set(message) == {'type', 'topics'}  # Never disclose entity data.
            return message
    pytest.fail(f'Missing invalidation for {topic}')


def test_users_tabs_devices_receive_task_creation_and_atomic_acceptance(client, admin_headers, driver_headers):
    with connect(client, admin_headers) as admin, connect(client, driver_headers) as driver, connect(client, driver_headers) as second_tab:
        authenticate(admin, admin_headers)
        authenticate(driver, driver_headers)
        authenticate(second_tab, driver_headers)
        response = client.post('/api/tasks', headers=admin_headers, json={
            'titulo': 'Coleta', 'endereco': 'Rua A', 'observacoes': 'Carga'})
        assert response.status_code == 201
        task_id = response.json()['id']
        for socket in (admin, driver, second_tab):
            invalidation(socket, 'tasks')
        assert client.post(f'/api/tasks/{task_id}/accept', headers=driver_headers).status_code == 200
        for socket in (admin, driver, second_tab):
            invalidation(socket, 'tasks')
        assert client.get('/api/tasks/available', headers=driver_headers).json() == []
        assert len(client.get('/api/tasks/mine', headers=driver_headers).json()) == 1


def test_rollback_noop_and_bulk_mutations():
    baseline = read_snapshot()[0]
    with SessionLocal() as db:
        vehicle = db.get(Vehicle, 1)
        vehicle.modelo = 'Rolled back'
        db.flush()
        db.rollback()
    assert read_snapshot()[0] == baseline
    with SessionLocal() as db:
        vehicle = db.get(Vehicle, 1)
        vehicle.modelo = vehicle.modelo
        db.commit()
    assert read_snapshot()[0] == baseline
    with SessionLocal() as db:
        db.execute(update(Vehicle).where(Vehicle.id == 1).values(modelo='Updated'))
        db.commit()
    changed = read_snapshot()[0]
    assert changed['vehicles'] != baseline['vehicles']
    with SessionLocal() as db:
        db.execute(delete(Vehicle).where(Vehicle.id == 1))
        db.commit()
    assert read_snapshot()[0]['vehicles'] != changed['vehicles']


def test_reconnection_syncs_changes_made_offline(client, admin_headers):
    with connect(client, admin_headers) as socket:
        authenticate(socket, admin_headers)
    with SessionLocal() as db:
        db.get(Vehicle, 1).modelo = 'Changed offline'
        db.commit()
    with connect(client, admin_headers) as socket:
        assert 'vehicles' in authenticate(socket, admin_headers)['topics']
        assert client.get('/api/vehicles/1', headers=admin_headers).json()['modelo'] == 'Changed offline'


def test_commit_from_another_process_reaches_connected_device(client, admin_headers):
    with connect(client, admin_headers) as socket:
        authenticate(socket, admin_headers)
        subprocess.run([sys.executable, '-c',
            'from app.core.database import SessionLocal; from app.models import Vehicle; '
            'db=SessionLocal(); db.get(Vehicle,1).modelo="Other worker"; db.commit(); db.close()'],
            check=True, capture_output=True, timeout=20)
        invalidation(socket, 'vehicles')
        assert client.get('/api/vehicles/1', headers=admin_headers).json()['modelo'] == 'Other worker'


@pytest.mark.parametrize('role', list(UserRole))
def test_profile_topic_allowlist(client, role):
    with SessionLocal() as db:
        db.get(User, 1).role = role
        db.commit()
    headers = {'Authorization': f'Bearer {create_access_token("1", role.value)}'}
    with connect(client, headers) as socket:
        assert set(authenticate(socket, headers)['topics']) == allowed_topics(role.value)
    if role == UserRole.MOTORISTA:
        assert 'tracking' not in allowed_topics(role.value)
        assert 'drivers' not in allowed_topics(role.value)


@pytest.mark.parametrize('change', ['disabled', 'role'])
def test_disabled_user_and_role_change_close_existing_connection(client, driver_headers, change):
    with connect(client, driver_headers) as socket:
        authenticate(socket, driver_headers)
        with SessionLocal() as db:
            account = db.get(User, 2)
            if change == 'disabled':
                account.ativo = False
            else:
                account.role = UserRole.COMPRAS
            db.commit()
        with pytest.raises(WebSocketDisconnect) as error:
            socket.receive_json()
        assert error.value.code == 4401


@pytest.mark.parametrize('token', ['invalid', create_access_token('999', 'ADMIN'),
    jwt.encode({'sub': '1'}, settings.secret_key, algorithm='HS256'), jwt.encode(
    {'sub': '1', 'exp': datetime.now(UTC) - timedelta(seconds=1)}, settings.secret_key, algorithm='HS256')])
def test_invalid_missing_user_and_expired_token_rejected(client, token):
    with client.websocket_connect('/api/realtime') as socket:
        socket.send_json({'token': token})
        with pytest.raises(WebSocketDisconnect) as error:
            socket.receive_json()
        assert error.value.code == 4401


def test_token_expiration_closes_live_socket(client):
    token = jwt.encode({'sub': '1', 'exp': datetime.now(UTC) + timedelta(seconds=3)},
                       settings.secret_key, algorithm='HS256')
    with client.websocket_connect('/api/realtime') as socket:
        authenticate(socket, {'Authorization': f'Bearer {token}'})
        with pytest.raises(WebSocketDisconnect) as error:
            # A heartbeat can be sent just before the expiration deadline.
            for _ in range(3):
                assert socket.receive_json()['type'] == 'heartbeat'
        assert error.value.code == 4401


def test_untrusted_origin_rejected(client):
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect('/api/realtime', headers={'origin': 'https://untrusted.invalid'}):
            pass
    assert error.value.code == 1008


def test_subscriber_cleanup(client, admin_headers):
    with connect(client, admin_headers) as socket:
        authenticate(socket, admin_headers)
        assert len(client.app.state.realtime.subscribers) == 1
    assert not client.app.state.realtime.subscribers


def test_driver_notifications_exclude_tracking_changes(client, driver_headers):
    from app.models.entities import VehicleTracking
    from app.models.tasks import Task
    with connect(client, driver_headers) as socket:
        authenticate(socket, driver_headers)
        with SessionLocal() as db:
            db.add(VehicleTracking(vehicle_id=1, provider='POSITRON', tracker_id='123', active=True))
            db.add(Task(titulo='Aviso', endereco='Rua A', observacoes='Teste', created_by=1))
            db.commit()
        message = invalidation(socket, 'tasks')
        assert 'tracking' not in message['topics']


def test_versions_are_bounded_per_module():
    with SessionLocal() as db:
        for index in range(10):
            db.get(Vehicle, 1).modelo = str(index)
            db.commit()
        assert db.query(RealtimeVersion).filter_by(topic='vehicles').count() == 1
