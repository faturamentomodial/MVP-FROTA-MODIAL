from datetime import timedelta
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import importlib.util
from pathlib import Path
import pytest
from sqlalchemy import select, func, create_engine, inspect, text
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.core.database import SessionLocal
from app.models import Driver, User, Vehicle, Trip
from app.models.enums import UserRole
from app.models.route_plans import RoutePlan, RoutePlanVersion
from app.models.route_templates import RouteTemplate, RouteExecution
from app.services import route_planning as provider
from app.services.route_scheduling import today
from test_route_plans import fake_matrix, fake_geometry


def point(i):
    return {'address': f'Rua Teste {i}, SP', 'latitude': -23.5+i/1000, 'longitude': -46.6}


def template_body(count=3):
    return {'name': 'Rota semanal', 'description': 'Região norte', 'origin': point(0),
            'return_point': point(99), 'addresses': [point(i+1) for i in range(count)],
            'weekdays': [0, 3], 'notes': 'Conferir portaria', 'profile': 'truck'}


def template(client, headers, monkeypatch, count=3):
    monkeypatch.setattr(provider, 'matrix', fake_matrix)
    monkeypatch.setattr(provider, 'geometry', fake_geometry)
    created = client.post('/api/route-templates', headers=headers, json=template_body(count))
    assert created.status_code == 201, created.text
    result = client.post(f"/api/route-templates/{created.json()['id']}/calculate", headers=headers,
                         json={'revision': 0})
    assert result.status_code == 200, result.text
    return result.json()


def booking(route, day=None, time='08:00', **overrides):
    return {'template_id': route['id'], 'template_revision': route['revision'],
            'date': (day or today()).isoformat(), 'departure_time': time,
            'driver_id': 1, 'vehicle_id': 1, 'request_key': str(uuid4()), **overrides}


def schedule(client, headers, body):
    return client.post('/api/route-executions', headers=headers, json=body)


def test_persistence_address_limit_return_optimization_and_revisions(client, admin_headers, monkeypatch):
    route = template(client, admin_headers, monkeypatch, 12)
    assert route['invoices'] == [] and len(route['addresses']) == 12
    assert 'driver_id' not in route and 'vehicle_id' not in route
    assert route['result']['algorithm'] == 'nearest-neighbour'
    assert route['result']['geometry']['coordinates'][-1] == [point(99)['longitude'], point(99)['latitude']]
    assert route['result']['warning'] and route['result']['truck_restrictions_supported'] is False
    url = f"/api/route-templates/{route['id']}"
    assert client.put(url, headers=admin_headers, json=template_body()).status_code == 409
    assert client.post(url+'/calculate', headers=admin_headers, json={'revision':0}).status_code == 409
    copied = client.post(url+'/duplicate', headers=admin_headers).json()
    assert copied['id'] != route['id'] and copied['addresses'] == route['addresses']
    with SessionLocal() as db:
        assert len(db.get(RouteTemplate, route['id']).data['addresses']) == 12
    for invalid in ({'weekdays':[7]}, {'weekdays':[0,0]}, {'addresses':[point(1)]*101},
                    {'invoices':[{'number':str(i), 'volumes':1, 'destination':point(i)} for i in range(11)], 'addresses':[]}):
        assert client.post('/api/route-templates', headers=admin_headers,
                           json={**template_body(), **invalid}).status_code == 422


def test_week_dates_idempotency_history_filters_reschedule_cancel(client, admin_headers, driver_headers, monkeypatch):
    route = template(client, admin_headers, monkeypatch)
    first_body = booking(route, time=None)
    first = schedule(client, admin_headers, first_body)
    assert first.status_code == 201, first.text
    first = first.json()
    assert client.delete(f"/api/route-plans/{first['plan_id']}?revision=0", headers=admin_headers).status_code == 409
    assert schedule(client, admin_headers, first_body).json()['id'] == first['id']
    assert schedule(client, admin_headers, {**first_body, 'notes':'changed'}).status_code == 409
    later_body = booking(route, today()+timedelta(days=7))
    second = schedule(client, admin_headers, later_body).json()
    assert first['plan_id'] != second['plan_id']
    assert len(client.get('/api/trips/planned', headers=driver_headers).json()) == 1
    assert client.get('/api/trips/planned', headers=driver_headers).json()[0]['id'] == first['plan_id']
    assert client.post('/api/trips', headers=driver_headers, json={
        'route_plan_id':second['plan_id'], 'vehicle_id':1, 'km_inicial':1000}).status_code == 409
    url = f"/api/route-templates/{route['id']}"
    assert client.put(url, headers=admin_headers, json={**template_body(1), 'revision':1, 'name':'Novo percurso'}).status_code == 200
    assert client.get(f"/api/route-executions/{first['id']}", headers=admin_headers).json()['snapshot']['name'] == 'Rota semanal'
    listing = f"/api/route-executions?date_from={today()}&date_to={today()}"
    assert [e['id'] for e in client.get(listing,headers=admin_headers).json()] == [first['id']]
    assert client.get(listing+'&driver_id=999',headers=admin_headers).json() == []
    assert client.get(listing+'&vehicle_id=999',headers=admin_headers).json() == []
    assert client.get(listing+'&status=FINALIZADA',headers=admin_headers).json() == []
    moved = client.put(f"/api/route-executions/{first['id']}",headers=admin_headers,
        json={**first_body, 'date':(today()+timedelta(days=1)).isoformat(), 'revision':0})
    assert moved.status_code == 200, moved.text
    assert moved.json()['snapshot']['addresses'] == first['snapshot']['addresses']
    assert client.put(f"/api/route-executions/{first['id']}",headers=admin_headers,json=first_body).status_code == 409
    cancel = f"/api/route-executions/{first['id']}/cancel"
    assert client.post(cancel,headers=admin_headers,json={'revision':1}).json()['status'] == 'CANCELADA'
    moved_listing = f"/api/route-executions?date_from={today()+timedelta(days=1)}&date_to={today()+timedelta(days=1)}"
    assert client.get(moved_listing, headers=admin_headers).json() == []
    cancelled = client.get(moved_listing+'&status=CANCELADA', headers=admin_headers).json()
    assert cancelled == []
    assert client.get(f"/api/route-executions/{first['id']}", headers=admin_headers).status_code == 404
    with SessionLocal() as db:
        assert db.get(RoutePlan, first['plan_id']) is None
        assert db.scalar(select(RoutePlanVersion.id).where(RoutePlanVersion.plan_id == first['plan_id'])) is None

    assert client.get('/api/route-plans',headers=admin_headers).json() == []


def test_driver_vehicle_overlap_all_day_cross_midnight_and_release(client, admin_headers, monkeypatch):
    route = template(client, admin_headers, monkeypatch)
    with SessionLocal() as db:
        db.add(Driver(nome='Outro', user=User(nome='Outro',email='other@example.com',senha_hash='unused',role=UserRole.MOTORISTA)))
        db.add(Vehicle(placa='XYZ9A88',marca='VW',modelo='Delivery',tipo='Baú',km_atual=0))
        db.commit()
    first = schedule(client,admin_headers,booking(route,time='23:30')).json()
    tomorrow = today()+timedelta(days=1)
    for body in (booking(route,time='23:50',driver_id=2), booking(route,time='23:50',vehicle_id=2),
                 booking(route,tomorrow,time='00:15'), booking(route,time=None)):
        assert schedule(client,admin_headers,body).status_code == 409
    assert schedule(client,admin_headers,booking(route,time='12:00')).status_code == 201
    assert schedule(client,admin_headers,booking(route,tomorrow,time='02:00')).status_code == 201
    assert client.post(f"/api/route-executions/{first['id']}/cancel",headers=admin_headers,json={'revision':0}).status_code == 200
    assert schedule(client,admin_headers,booking(route,time='23:30')).status_code == 201


@pytest.mark.parametrize('address_only',[True,False])
def test_existing_trip_lifecycle_snapshot_delivery_occurrence_and_no_duplicate(client,admin_headers,driver_headers,monkeypatch,address_only):
    route = template(client,admin_headers,monkeypatch,2)
    if not address_only:
        body={**template_body(0), 'invoices':[{'number':'123','volumes':4,'destination':point(1)}], 'revision':1}
        url=f"/api/route-templates/{route['id']}"
        assert client.put(url,headers=admin_headers,json=body).status_code == 200
        route=client.post(url+'/calculate',headers=admin_headers,json={'revision':2}).json()
    execution=schedule(client,admin_headers,booking(route)).json()
    body={'route_plan_id':execution['plan_id'],'vehicle_id':1,'km_inicial':1000}
    trip=client.post('/api/trips',headers=driver_headers,json=body)
    assert trip.status_code == 201,trip.text
    trip=trip.json();tid=trip['id']
    assert trip['total_volumes'] == (0 if address_only else 4)
    assert all(n['is_address_stop']==address_only for n in trip['notas'])
    assert client.post('/api/trips',headers=driver_headers,json=body).status_code == 409
    eurl=f"/api/route-executions/{execution['id']}"
    assert client.get(eurl,headers=admin_headers).json()['status']=='EM_ANDAMENTO'
    assert client.put(eurl,headers=admin_headers,json=booking(route)).status_code == 409
    assert client.post(eurl+'/cancel',headers=admin_headers,json={'revision':0}).status_code == 409
    assert client.put(f'/api/trips/{tid}/cargo',headers=admin_headers,json={'notas':[{'numero_nota':'changed','volumes':1}]}).status_code == 409
    assert client.put(f'/api/trips/{tid}/delivery-order',headers=admin_headers,json={'invoice_ids':[n['id'] for n in trip['notas']],'revision':0}).status_code == 409
    assert client.post(f'/api/trips/{tid}/start',headers=driver_headers).status_code == 400
    items=client.get('/api/checklist-items',headers=driver_headers).json()
    assert client.post(f'/api/trips/{tid}/checklist',headers=driver_headers,json={
        'answers':[{'checklist_item_id':i['id'],'status':'OK'} for i in items]}).status_code == 201
    assert client.post(f'/api/trips/{tid}/start',headers=driver_headers).status_code == 200
    assert client.post(f'/api/trips/{tid}/finish',headers=driver_headers,json={'km_final':1100}).status_code == 409
    for i,n in enumerate(trip['notas']):
        url=f"/api/trips/{tid}/deliveries/{n['id']}"
        assert client.post(url+'/start',headers=driver_headers).status_code == 200
        response=client.post(url+('/occurrence' if i else '/finish'),headers=driver_headers,
            json={'motivo':'CLIENTE_FECHADO'} if i else {})
        assert response.status_code == 200,response.text
    assert client.post(f'/api/trips/{tid}/finish',headers=driver_headers,json={'km_final':1100}).status_code == 200
    assert client.get(eurl,headers=admin_headers).json()['status']=='FINALIZADA'
    assert client.post('/api/trips',headers=driver_headers,json=body).status_code == 409
    assert client.get(f"/api/route-templates/{route['id']}",headers=admin_headers).json()['result']
    assert schedule(client,admin_headers,booking(route)).status_code == 201
    with SessionLocal() as db:
        assert db.scalar(select(func.count(Trip.id))) == 1


def test_reschedule_assignment_uses_snapshot_and_local_date(client,admin_headers,driver_headers,monkeypatch):
    route=template(client,admin_headers,monkeypatch)
    original=booking(route,time='00:15')
    execution=schedule(client,admin_headers,original).json()
    with SessionLocal() as db:
        db.add(Driver(nome='Outro', user=User(nome='Outro',email='other@example.com',senha_hash='unused',role=UserRole.MOTORISTA)))
        db.add(Vehicle(placa='XYZ9A88',marca='VW',modelo='Delivery',tipo='Baú',km_atual=0))
        db.commit()
    moved=client.put(f"/api/route-executions/{execution['id']}",headers=admin_headers,
        json={**original,'driver_id':2,'vehicle_id':2,'departure_time':'23:45'})
    assert moved.status_code == 200,moved.text
    assert moved.json()['snapshot']['vehicle_id'] == 2
    assert moved.json()['snapshot']['origin'] == execution['snapshot']['origin']
    assert client.get('/api/trips/planned',headers=driver_headers).json() == []
    assert client.post('/api/trips',headers=driver_headers,json={
        'route_plan_id':execution['plan_id'],'vehicle_id':1,'km_inicial':1000}).status_code == 403
    listing=client.get(f'/api/route-executions?date_from={today()}&date_to={today()}',headers=admin_headers).json()
    assert listing[0]['date'] == today().isoformat() and listing[0]['departure_time'] == '23:45'
    assert client.get(f"/api/route-templates/{route['id']}",headers=admin_headers).json()['revision'] == 1


def test_permissions_inactive_invalid_stale_and_provider_atomicity(client,admin_headers,driver_headers,monkeypatch):
    route=template(client,admin_headers,monkeypatch)
    for path in ('/route-templates','/route-templates/1','/route-executions/1',f'/route-executions?date_from={today()}&date_to={today()}'):
        assert client.get('/api'+path).status_code == 401
        assert client.get('/api'+path,headers=driver_headers).status_code == 403
    for path,body in (('/route-templates',template_body()),('/route-executions',booking(route))):
        assert client.post('/api'+path,headers=driver_headers,json=body).status_code == 403
    for overrides in ({'driver_id':999},{'vehicle_id':999},{'template_revision':0}, {'date':(today()-timedelta(days=1)).isoformat()}):
        assert schedule(client,admin_headers,booking(route,**overrides)).status_code in (409,422)
    from fastapi import HTTPException
    def fail(*args): raise HTTPException(503,'Unavailable')
    monkeypatch.setattr(provider,'geometry',fail)
    url=f"/api/route-templates/{route['id']}"
    assert client.post(url+'/calculate',headers=admin_headers,json={'revision':1}).status_code == 503
    assert client.get(url,headers=admin_headers).json()['revision'] == 1
    assert client.put(url,headers=admin_headers,json={**template_body(), 'revision':1, 'active':False}).status_code == 200
    assert schedule(client,admin_headers,booking(route,template_revision=2)).status_code == 422


def test_concurrent_schedule_conflict_and_trip_claim(client,admin_headers,driver_headers,monkeypatch):
    route=template(client,admin_headers,monkeypatch)
    def create(_): return schedule(client,admin_headers,booking(route)).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(create,range(2))) == [201,409]
    plan=client.get('/api/trips/planned',headers=driver_headers).json()[0]
    def start(_): return client.post('/api/trips',headers=driver_headers,json={'route_plan_id':plan['id'],'vehicle_id':1,'km_inicial':1000}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(start,range(2))) == [201,409]


def test_incremental_migration_preserves_existing_records():
    spec=importlib.util.spec_from_file_location('templates_migration',Path('migrations/versions/20261105_0016_route_templates.py'))
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    engine=create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY)'))
        conn.execute(text('CREATE TABLE drivers (id INTEGER PRIMARY KEY)'))
        conn.execute(text('CREATE TABLE vehicles (id INTEGER PRIMARY KEY)'))
        conn.execute(text('CREATE TABLE route_plans (id INTEGER PRIMARY KEY, data JSON)'))
        conn.execute(text('CREATE TABLE trip_invoices (id INTEGER PRIMARY KEY, volumes INTEGER NOT NULL, CONSTRAINT ck_trip_invoice_positive_volumes CHECK (volumes > 0))'))
        conn.execute(text("INSERT INTO route_plans VALUES (1, '{}')"))
        conn.execute(text('INSERT INTO trip_invoices VALUES (1, 3)'))
        migration.op=Operations(MigrationContext.configure(conn))
        migration.upgrade()
        migration.upgrade()  # Fresh installs use current metadata in migration 1.
        assert conn.execute(text('SELECT volumes, is_address_stop FROM trip_invoices')).one() == (3,0)
        assert conn.execute(text('SELECT count(*) FROM route_plans')).scalar() == 1
        assert 'route_templates' in inspect(conn).get_table_names()
        migration.downgrade()
        assert conn.execute(text('SELECT volumes FROM trip_invoices')).scalar() == 3


def test_delete_template_removes_unstarted_executions(client, admin_headers, driver_headers, monkeypatch):
    route = template(client, admin_headers, monkeypatch)
    execution = schedule(client, admin_headers, booking(route)).json()
    url = f"/api/route-templates/{route['id']}"
    assert client.delete(url, params={'revision': route['revision']}, headers=driver_headers).status_code == 403
    assert client.delete(url, params={'revision': 0}, headers=admin_headers).status_code == 409
    assert client.get(url, headers=admin_headers).status_code == 200
    assert client.delete(url, params={'revision': route['revision']}, headers=admin_headers).status_code == 204
    assert client.get('/api/route-templates', headers=admin_headers).json() == []
    listing = f"/api/route-executions?date_from={today()}&date_to={today()}"
    assert client.get(listing, headers=admin_headers).json() == []
    assert client.get(listing+'&status=PROGRAMADA', headers=admin_headers).json() == []
    assert client.get(url, headers=admin_headers).status_code == 404
    assert client.post(url+'/duplicate', headers=admin_headers).status_code == 404
    assert client.put(url, headers=admin_headers, json={**template_body(), 'revision': route['revision']+1}).status_code == 404
    assert schedule(client, admin_headers, booking(route, today()+timedelta(days=1))).status_code == 404
    saved = client.get(f"/api/route-executions/{execution['id']}", headers=admin_headers)
    assert saved.status_code == 404
    with SessionLocal() as db:
        assert db.get(RouteTemplate, route['id']) is None
        assert db.get(RouteExecution, execution['id']) is None
        assert db.get(RoutePlan, execution['plan_id']) is None
        assert db.scalar(select(RoutePlanVersion.id).where(RoutePlanVersion.plan_id == execution['plan_id'])) is None


def test_delete_template_without_executions(client, admin_headers):
    route = client.post('/api/route-templates', headers=admin_headers, json=template_body()).json()
    url = f"/api/route-templates/{route['id']}"
    assert client.delete(url, params={'revision': 0}, headers=admin_headers).status_code == 204
    assert client.delete(url, params={'revision': 0}, headers=admin_headers).status_code == 404
    assert client.get('/api/route-templates', headers=admin_headers).json() == []


def test_delete_template_keeps_started_trip(client, admin_headers, driver_headers, monkeypatch):
    route = template(client, admin_headers, monkeypatch)
    execution = schedule(client, admin_headers, booking(route)).json()
    trip = client.post('/api/trips', headers=driver_headers, json={
        'route_plan_id': execution['plan_id'], 'vehicle_id': 1, 'km_inicial': 1000})
    assert trip.status_code == 201
    future = schedule(client, admin_headers, booking(route, today()+timedelta(days=1))).json()
    url = f"/api/route-templates/{route['id']}"
    assert client.delete(url, params={'revision': route['revision']}, headers=admin_headers).status_code == 204
    assert client.get(f"/api/route-executions/{execution['id']}", headers=admin_headers).status_code == 200
    assert client.get(f"/api/route-executions/{future['id']}", headers=admin_headers).status_code == 404
    with SessionLocal() as db:
        assert db.get(Trip, trip.json()['id']) is not None
        assert db.get(RoutePlan, execution['plan_id']) is not None
        assert db.get(RoutePlan, future['plan_id']) is None
