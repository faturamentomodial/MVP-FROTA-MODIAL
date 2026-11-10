from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from app.core.database import SessionLocal
from app.models import Occurrence, Vehicle
from app.services.realtime import RealtimeVersion


def create(client, headers, **extra):
    response = client.post('/api/occurrences', headers=headers, json={
        'vehicle_id': 1, 'tipo': 'PROBLEMA_MECANICO', 'descricao': 'Troca de ?leo do veículo', **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_history_link_update_summary_and_filters(client, admin_headers, driver_headers):
    common = create(client, driver_headers)
    first = create(client, driver_headers, maintenance_type='PREVENTIVA', maintenance_cost='125.50', maintenance_km=1000)
    second = create(client, driver_headers, maintenance_type='EMERGENCIAL', maintenance_cost='0.00')
    with SessionLocal() as db:
        old_version = db.get(RealtimeVersion, 'occurrences').version
    changed = client.patch(f"/api/occurrences/{first['id']}", headers=admin_headers, json={
        'status': 'RESOLVIDA', 'maintenance_responsible': 'Oficina', 'maintenance_cost': '150.25'})
    assert changed.status_code == 200, changed.text
    completed = changed.json()['maintenance_completed_at']
    assert completed
    with SessionLocal() as db:
        assert db.get(RealtimeVersion, 'occurrences').version != old_version
        assert db.scalar(select(func.count()).select_from(Occurrence)) == 3
        db.get(Occurrence, first['id']).data_hora = datetime(2025, 1, 1, tzinfo=UTC)
        db.commit()
    url = '/api/vehicles/1/maintenance'
    history = client.get(url, headers=admin_headers).json()
    assert [o['id'] for o in history['items']] == [second['id'], first['id']]
    assert history['summary']['total'] == 2
    assert history['summary']['pending'] == 1
    assert Decimal(str(history['summary']['cost'])) == Decimal('150.25')
    assert history['summary']['last_completed_at']
    assert client.get(url+'?maintenance_type=PREVENTIVA&status=RESOLVIDA', headers=admin_headers).json()['total'] == 1
    assert client.get(url+'?date_to=2025-01-02T00:00:00Z', headers=admin_headers).json()['total'] == 1
    assert client.get(url+'?date_from=2025-01-02T00:00:00Z', headers=admin_headers).json()['total'] == 1
    paged = client.get(url+'?page_size=1&page=2', headers=admin_headers).json()
    assert paged['pages'] == 2 and paged['items'][0]['id'] == first['id']
    assert paged['summary'] == history['summary']
    assert client.get(f"/api/occurrences/{common['id']}", headers=admin_headers).json()['maintenance_type'] is None
    assert client.get(f"/api/occurrences/{first['id']}", headers=admin_headers).json()['vehicle_id'] == 1
    client.patch(f"/api/occurrences/{first['id']}", headers=admin_headers, json={'status':'EM_ANALISE'})
    assert client.get(url, headers=admin_headers).json()['summary']['last_completed_at'] is None
    client.patch(f"/api/occurrences/{second['id']}", headers=admin_headers, json={'maintenance_type':None})
    assert client.get(url, headers=admin_headers).json()['total'] == 1


def test_permissions_isolation_and_validation(client, admin_headers, driver_headers):
    create(client, driver_headers, maintenance_type='CORRETIVA')
    with SessionLocal() as db:
        db.add(Vehicle(placa='XYZ9A99', marca='VW', modelo='Outro', tipo='Van', km_atual=0))
        db.commit()
    assert client.get('/api/vehicles/2/maintenance', headers=admin_headers).json()['total'] == 0
    assert client.get('/api/vehicles/999/maintenance', headers=admin_headers).status_code == 404
    assert client.get('/api/vehicles/1/maintenance', headers=driver_headers).status_code == 403
    assert client.get('/api/vehicles/1/maintenance').status_code == 401
    for query in ('maintenance_type=OUTRO','status=INVALIDO','page_size=101','date_from=2026-01-02&date_to=2026-01-01'):
        assert client.get('/api/vehicles/1/maintenance?'+query, headers=admin_headers).status_code == 422
    for metadata in ({'maintenance_cost':-1}, {'maintenance_km':-1}, {'maintenance_type':'OUTRO'}):
        assert client.post('/api/occurrences', headers=driver_headers, json={
            'vehicle_id':1, 'tipo':'OUTRO', 'descricao':'Teste', **metadata}).status_code == 422
    assert client.patch('/api/occurrences/1', headers=driver_headers, json={'maintenance_type':'PREVENTIVA'}).status_code == 403
    assert client.patch('/api/occurrences/1', headers=admin_headers, json={'status':None}).status_code == 422


def test_purchasing_cannot_read_vehicle_history(client):
    from app.models import User
    from app.models.enums import UserRole
    from app.core.security import get_password_hash
    from conftest import login
    with SessionLocal() as db:
        db.add(User(nome='Compras', email='compras@test.com', senha_hash=get_password_hash('Compras@123'), role=UserRole.COMPRAS))
        db.commit()
    headers = login(client, 'compras@test.com', 'Compras@123')
    assert client.get('/api/vehicles/1/maintenance', headers=headers).status_code == 403


def test_maintenance_migration_preserves_original_rows(monkeypatch, tmp_path):
    from pathlib import Path
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect, text
    from app.core.config import settings
    url = f"sqlite+pysqlite:///{tmp_path.as_posix()}/maintenance.db"
    monkeypatch.setattr(settings, 'database_url', url)
    config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    config.set_main_option('script_location', str(Path(__file__).resolve().parents[1] / 'migrations'))
    command.upgrade(config, '20261110_0021')
    engine = create_engine(url)
    # Initial migration imports current metadata, so downgrade ensures a real pre-feature schema.
    command.stamp(config, '20261110_0022')
    command.downgrade(config, '20261110_0021')
    with engine.begin() as db:
        db.execute(text("INSERT INTO users (id,nome,email,senha_hash,role,ativo,created_at,updated_at) VALUES (1,'Motorista','old@test.com','hash','MOTORISTA',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        db.execute(text("INSERT INTO drivers (id,nome,user_id,ativo,created_at,updated_at) VALUES (1,'Motorista',1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        db.execute(text("INSERT INTO vehicles (id,placa,marca,modelo,tipo,km_atual,status,ativo,created_at,updated_at) VALUES (1,'ABC1234','VW','Van','Van',100,'DISPONIVEL',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        db.execute(text("INSERT INTO occurrences (id,driver_id,vehicle_id,tipo,descricao,data_hora,status,created_at,updated_at) VALUES (1,1,1,'PROBLEMA_MECANICO','Legado',CURRENT_TIMESTAMP,'RESOLVIDA',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        before = dict(db.execute(text('SELECT * FROM occurrences')).mappings().one())
    command.upgrade(config, 'head')
    with engine.connect() as db:
        after = dict(db.execute(text('SELECT * FROM occurrences')).mappings().one())
        assert all(after[key] == value for key,value in before.items())
        assert after['maintenance_type'] is None
        assert after['maintenance_completed_at'] is None
    assert 'maintenance_cost' in {c['name'] for c in inspect(engine).get_columns('occurrences')}
    engine.dispose()
