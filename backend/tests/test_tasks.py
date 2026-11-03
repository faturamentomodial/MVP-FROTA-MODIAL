from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.main import app
from app.models import Driver, Task, User
from app.models.enums import UserRole
from conftest import login


def create(client, headers):
    response = client.post('/api/tasks', headers=headers, json={'titulo':'Coleta', 'endereco':'Rua Central, 10', 'observacoes':'Retirar documentos'})
    assert response.status_code == 201, response.text
    return response.json()


def second_driver(client):
    with SessionLocal() as db:
        user = User(nome='Outro', email='other@example.com', senha_hash=get_password_hash('Driver@123'), role=UserRole.MOTORISTA)
        db.add(Driver(nome='Outro', user=user))
        db.commit()
    return login(client, 'other@example.com', 'Driver@123')


def test_lifecycle(client, admin_headers, driver_headers):
    task = create(client, admin_headers)
    tid = task['id']
    assert task['status'] == 'DISPONIVEL'
    assert client.get('/api/tasks/available', headers=driver_headers).json()[0]['id'] == tid
    assert client.post(f'/api/tasks/{tid}/complete', headers=driver_headers).status_code == 403
    accepted = client.post(f'/api/tasks/{tid}/accept', headers=driver_headers)
    assert accepted.status_code == 200
    assert accepted.json()['accepted_at']
    assert client.get('/api/tasks/available', headers=driver_headers).json() == []
    assert len(client.get('/api/tasks/mine', headers=driver_headers).json()) == 1
    assert client.post(f'/api/tasks/{tid}/accept', headers=driver_headers).status_code == 409
    completed = client.post(f'/api/tasks/{tid}/complete', headers=driver_headers)
    assert completed.status_code == 200
    timestamp = completed.json()['completed_at']
    assert timestamp and completed.json()['status'] == 'CONCLUIDA'
    assert client.post(f'/api/tasks/{tid}/complete', headers=driver_headers).status_code == 409
    assert client.get(f'/api/tasks/{tid}', headers=driver_headers).json()['completed_at'] == timestamp
    assert client.get('/api/tasks/available', headers=driver_headers).json() == []
    assert client.get('/api/tasks/mine', headers=driver_headers).json() == []
    assert client.get('/api/tasks/mine?completed=true', headers=driver_headers).json()[0]['id'] == tid
    assert client.get('/api/tasks?status=CONCLUIDA', headers=admin_headers).json()[0]['driver_name']


def test_permissions_and_validation(client, admin_headers, driver_headers):
    other = second_driver(client)
    tid = create(client, admin_headers)['id']
    assert client.get('/api/tasks').status_code == 401
    assert client.get('/api/tasks', headers=driver_headers).status_code == 403
    assert client.post('/api/tasks', headers=driver_headers, json={}).status_code == 403
    assert client.post('/api/tasks', headers=admin_headers, json={'titulo':' ', 'endereco':'x', 'observacoes':'x'}).status_code == 422
    assert client.post('/api/tasks', headers=admin_headers, json={'titulo':'x','endereco':'x','observacoes':'x','driver_id':1}).status_code == 422
    assert client.post(f'/api/tasks/{tid}/accept', headers=admin_headers).status_code == 403
    assert client.post(f'/api/tasks/{tid}/accept', headers=driver_headers).status_code == 200
    assert client.post(f'/api/tasks/{tid}/accept', headers=other).status_code == 409
    assert client.post(f'/api/tasks/{tid}/complete', headers=other).status_code == 403
    assert client.get(f'/api/tasks/{tid}', headers=other).status_code == 403
    assert client.get('/api/tasks/mine', headers=other).json() == []
    assert client.get('/api/tasks/mine?completed=true', headers=other).json() == []
    assert client.get('/api/tasks/9999', headers=admin_headers).status_code == 404
    with SessionLocal() as db:
        driver = db.scalar(select(Driver).where(Driver.user_id == 2))
        driver.ativo = False
        db.commit()
    assert client.get('/api/tasks/available', headers=driver_headers).status_code == 403
    assert client.post(f'/api/tasks/{tid}/complete', headers=driver_headers).status_code == 403


def test_simultaneous_acceptance(client, admin_headers, driver_headers):
    other = second_driver(client)
    tid = create(client, admin_headers)['id']
    barrier = Barrier(2)
    def accept(headers):
        with TestClient(app) as concurrent_client:
            barrier.wait(timeout=10)
            return concurrent_client.post(f'/api/tasks/{tid}/accept', headers=headers)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(accept, headers) for headers in (driver_headers, other)]
        responses = [future.result(timeout=20) for future in futures]
    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response.json()['driver_id'] for response in responses if response.status_code == 200)
    with SessionLocal() as db:
        assert db.get(Task, tid).driver_id == winner


def test_in_progress_can_complete(client, admin_headers, driver_headers):
    tid = create(client, admin_headers)['id']
    client.post(f'/api/tasks/{tid}/accept', headers=driver_headers)
    with SessionLocal() as db:
        task = db.get(Task, tid)
        task.status = 'EM_ANDAMENTO'
        db.commit()
    assert client.post(f'/api/tasks/{tid}/complete', headers=driver_headers).status_code == 200


def test_task_does_not_change_current_route(client, admin_headers, driver_headers):
    from conftest import assigned_plan
    from app.models import Trip
    plan_id = assigned_plan()
    response = client.post('/api/trips', headers=driver_headers, json={'route_plan_id':plan_id, 'vehicle_id':1, 'km_inicial':1000})
    assert response.status_code == 201
    trip_id = response.json()['id']
    with SessionLocal() as db:
        trip = db.get(Trip, trip_id)
        before = (trip.status, trip.delivery_revision, [(i.id, i.status, i.numero_nota) for i in trip.invoices])
    tid = create(client, admin_headers)['id']
    assert client.post(f'/api/tasks/{tid}/accept', headers=driver_headers).status_code == 200
    assert client.post(f'/api/tasks/{tid}/complete', headers=driver_headers).status_code == 200
    with SessionLocal() as db:
        trip = db.get(Trip, trip_id)
        after = (trip.status, trip.delivery_revision, [(i.id, i.status, i.numero_nota) for i in trip.invoices])
    assert before == after
