from copy import deepcopy
import importlib.util
from pathlib import Path
import pytest
from sqlalchemy import create_engine, inspect, text
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.services import route_planning as provider
from test_route_plans import fake_matrix, fake_geometry


def note(id='n1', number='100', company='1', pending=False):
    return dict(id=id, number=number, volumes=3, partner='Cliente', company=company, series='A', source='SANKHYA', external_id=id,
                address='Rua Teste 10, São Paulo', destination=None if pending else dict(address='Rua Teste 10, São Paulo', latitude=-23.5, longitude=-46.6), geocode_status='PENDENTE' if pending else 'VALIDADO')


def route(key='r1', ids=None):
    return dict(key=key, plan_id=None, color='#002fa7', invoice_ids=ids or [], plan=dict(name=key, revision=0, driver_id=1, vehicle_id=1, profile='truck', origin=dict(address='Origem de teste', latitude=-23.6, longitude=-46.7), invoices=[], objective='duration'))


def body(work):
    result = {k: deepcopy(work[k]) for k in ('name', 'revision', 'notes', 'routes')}
    for r in result['routes']:
        r.pop('delivery_statuses', None)
        r.pop('resource_warnings', None)
        r['plan'] = {k: v for k, v in r['plan'].items() if k in ('name', 'revision', 'driver_id', 'vehicle_id', 'profile', 'origin', 'invoices', 'objective')}
        r['plan']['invoices'] = []
    return result


def create(client, headers):
    response = client.post('/api/distributions', headers=headers, json={'name': 'Distribuição teste'})
    assert response.status_code == 201, response.text
    work = response.json()
    return f"/api/distributions/{work['id']}", work


def put(client, headers, url, data, expected=200):
    response = client.put(url, headers=headers, json=data)
    assert response.status_code == expected, response.text
    return response.json()


def test_pool_persistence_multi_routes_transfer_concurrency_history(client, admin_headers):
    url, work = create(client, admin_headers)
    data = body(work)
    data['notes'] = [note(), note('n2', '101'), note('pending', '102', pending=True)]
    data['routes'] = [route(ids=['n1']), route('r2')]
    work = put(client, admin_headers, url, data)
    assert len(work['routes']) == 2
    assert client.get(url, headers=admin_headers).json() == work
    assert work['notes'][2]['destination'] is None
    # Two editors read revision 1: only the first edit is accepted.
    stale = body(work)
    data = body(work)
    data['routes'][0]['invoice_ids'] = []
    data['routes'][1]['invoice_ids'] = ['n1', 'n2']
    work = put(client, admin_headers, url, data)
    put(client, admin_headers, url, stale, 409)
    assert work['routes'][0]['plan']['invoices'] == []
    assert len(work['routes'][1]['plan']['invoices']) == 2
    assert len(client.get(url+'/versions', headers=admin_headers).json()) == 3
    data = body(work)
    data['routes'][0]['invoice_ids'] = ['n1']
    put(client, admin_headers, url, data, 422)
    assert client.get(url, headers=admin_headers).json()['revision'] == 2
    data = body(work)
    data['routes'][0]['invoice_ids'] = ['pending']
    put(client, admin_headers, url, data, 422)


def test_invoice_identity_duplicate_and_same_number_other_company(client, admin_headers):
    url, work = create(client, admin_headers)
    data = body(work)
    data['notes'] = [note(), {**note(), 'id': 'copy'}]
    put(client, admin_headers, url, data, 422)
    data['notes'] = [note(), note('n2', '100', '2')]
    data['routes'] = [route(ids=['n1']), route('r2', ['n2'])]
    work = put(client, admin_headers, url, data)
    assert len(work['notes']) == 2
    data = body(work)
    data['routes'][0]['invoice_ids'] = ['n1', 'n2']
    data['routes'][1]['invoice_ids'] = []
    put(client, admin_headers, url, data, 422)
    # Manual identity uses normalized company, series and number, not random UUID.
    data = body(work)
    data['routes'] = [{**r, 'invoice_ids': []} for r in data['routes']]
    manual = {**note(), 'source': 'MANUAL', 'external_id': None}
    data['notes'] = [manual, {**manual, 'id': 'copy'}]
    put(client, admin_headers, url, data, 422)


def test_calculation_confirmation_driver_flow_and_immutable_assignment(client, admin_headers, driver_headers, monkeypatch):
    monkeypatch.setattr(provider, 'matrix', fake_matrix)
    monkeypatch.setattr(provider, 'geometry', fake_geometry)
    url, work = create(client, admin_headers)
    data = body(work)
    data['notes'] = [note(), note('n2', '101')]
    data['routes'] = [route(ids=['n1', 'n2']), route('r2')]
    work = put(client, admin_headers, url, data)
    plan_id = work['routes'][0]['plan_id']
    plan_url = f'/api/route-plans/{plan_id}'
    assert client.put(plan_url, headers=admin_headers, json=body(work)['routes'][0]['plan']).status_code == 409
    for optimize in (False, True):
        rev = work['routes'][0]['plan']['revision']
        result = client.post(plan_url+'/calculate', headers=admin_headers, json={'revision': rev, 'optimize': optimize})
        assert result.status_code == 200, result.text
        work = client.get(url, headers=admin_headers).json()
        assert work['routes'][0]['plan']['result']['algorithm'] == ('held-karp' if optimize else 'manual')
    stale = body(work)
    rev = work['routes'][0]['plan']['revision']
    response = client.post(plan_url+'/confirm', headers=admin_headers, json={'revision': rev})
    assert response.status_code == 200
    put(client, admin_headers, url, stale, 409)
    work = client.get(url, headers=admin_headers).json()
    # Can still edit a separate draft after confirmation.
    data = body(work)
    data['routes'][1]['plan']['name'] = 'Outra rota'
    work = put(client, admin_headers, url, data)
    for mutation in ('transfer', 'note', 'color', 'origin'):
        data = body(work)
        if mutation == 'transfer':
            data['routes'][0]['invoice_ids'] = ['n2']
            data['routes'][1]['invoice_ids'] = ['n1']
        elif mutation == 'note':
            data['notes'][0]['volumes'] = 50
        elif mutation == 'color':
            data['routes'][0]['color'] = '#ffffff'
        else:
            data['routes'][0]['plan']['origin']['latitude'] = -20
        put(client, admin_headers, url, data, 409)
    assert client.get('/api/trips/planned', headers=driver_headers).json()[0]['id'] == plan_id
    trip = client.post('/api/trips', headers=driver_headers, json={'route_plan_id': plan_id, 'vehicle_id': 1, 'km_inicial': 1000})
    assert trip.status_code == 201, trip.text
    assert len(trip.json()['notas']) == 2
    work = client.get(url, headers=admin_headers).json()
    assert work['routes'][0]['delivery_statuses'] == {'100': 'PENDENTE', '101': 'PENDENTE'}
    # Changes to another draft remain possible after the trip starts.
    put(client, admin_headers, url, body(work))
    assert work['routes'][1]['resource_warnings']
    trip_id = trip.json()['id']
    items = client.get('/api/checklist-items', headers=driver_headers).json()
    assert client.post(f'/api/trips/{trip_id}/checklist', headers=driver_headers, json={'answers': [{'checklist_item_id': i['id'], 'status': 'OK'} for i in items]}).status_code == 201
    assert client.post(f'/api/trips/{trip_id}/start', headers=driver_headers).status_code == 200
    for invoice in trip.json()['notas']:
        delivery_url = f"/api/trips/{trip_id}/deliveries/{invoice['id']}"
        assert client.post(delivery_url+'/start', headers=driver_headers).status_code == 200
        assert client.post(delivery_url+'/finish', headers=driver_headers).status_code == 200
    work = client.get(url, headers=admin_headers).json()
    assert set(work['routes'][0]['delivery_statuses'].values()) == {'ENTREGUE'}
    assert client.post(f'/api/trips/{trip_id}/finish', headers=driver_headers, json={'km_final': 1100}).status_code == 200

def test_invalid_assignments_limits_access_and_inactive_resources(client, admin_headers, driver_headers):
    assert client.get('/api/distributions').status_code == 401
    assert client.get('/api/distributions', headers=driver_headers).status_code == 403
    assert client.post('/api/distributions', headers=driver_headers, json={'name':'X'}).status_code == 403
    url, work = create(client, admin_headers)
    assert client.get(url, headers=driver_headers).status_code == 403
    assert client.put(url, headers=driver_headers, json=body(work)).status_code == 403
    data = body(work)
    data['notes'] = [note()]
    data['routes'] = [route(ids=['n1'])]
    data['routes'][0]['plan']['driver_id'] = 999
    put(client, admin_headers, url, data, 422)
    data['routes'][0]['plan']['driver_id'] = 1
    data['routes'][0]['plan']['vehicle_id'] = 999
    put(client, admin_headers, url, data, 422)
    data['routes'][0]['plan']['vehicle_id'] = 1
    data['routes'][0]['plan_id'] = 1
    put(client, admin_headers, url, data, 409)
    data['routes'] = [route(ids=[f'n{i}' for i in range(11)])]
    data['notes'] = [note(f'n{i}', str(i)) for i in range(11)]
    put(client, admin_headers, url, data, 422)
    # Visualization/distribution pool itself is not subject to the TSP limit.
    data['routes'] = []
    assert len(put(client, admin_headers, url, data)['notes']) == 11


def test_calculation_failure_rolls_back_and_plan_race(client, admin_headers, monkeypatch):
    from fastapi import HTTPException
    url, work = create(client, admin_headers)
    data = body(work); data['notes'] = [note()]; data['routes'] = [route(ids=['n1'])]
    work = put(client, admin_headers, url, data)
    plan_url = f"/api/route-plans/{work['routes'][0]['plan_id']}"
    def unavailable(*args):
        raise HTTPException(429, 'Limite do provedor')
    monkeypatch.setattr(provider, 'matrix', unavailable)
    assert client.post(plan_url+'/calculate', headers=admin_headers, json={'revision': 0}).status_code == 429
    assert client.get(url, headers=admin_headers).json() == work
    monkeypatch.setattr(provider, 'matrix', fake_matrix)
    monkeypatch.setattr(provider, 'geometry', fake_geometry)
    assert client.post(plan_url+'/calculate', headers=admin_headers, json={'revision': 0}).status_code == 200
    put(client, admin_headers, url, body(work), 409)


def test_additive_distribution_migration_real_schema():
    spec = importlib.util.spec_from_file_location('distribution_migration', Path('migrations/versions/20261104_0012_distributions.py'))
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('PRAGMA foreign_keys=ON'))
        connection.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY)'))
        connection.execute(text('CREATE TABLE route_plans (id INTEGER PRIMARY KEY)'))
        connection.execute(text('INSERT INTO users VALUES (1)'))
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert {'distributions', 'distribution_versions', 'distribution_routes'}.issubset(inspect(connection).get_table_names())
        assert inspect(connection).get_foreign_keys('distribution_routes')
        assert inspect(connection).get_unique_constraints('distribution_versions')
        migration.upgrade()  # Fresh-install metadata path is idempotent.
        migration.downgrade()
        assert set(inspect(connection).get_table_names()) == {'users', 'route_plans'}
        assert connection.execute(text('SELECT id FROM users')).scalar() == 1


def test_full_alembic_chain_isolated_development_database(tmp_path, monkeypatch):
    from alembic import command
    from alembic.config import Config
    from app.core.config import settings
    database = tmp_path / 'distribution_migration.db'
    monkeypatch.setattr(settings, 'database_url', f'sqlite:///{database.as_posix()}')
    config = Config('alembic.ini')
    command.upgrade(config, '20261104_0011')
    isolated = create_engine(settings.database_url)
    with isolated.begin() as connection:
        # The historical initial migration creates current metadata. Remove only
        # the three empty new tables in this isolated DB to emulate an old install.
        for table in ('distribution_routes', 'distribution_versions', 'distributions'):
            connection.execute(text(f'DROP TABLE {table}'))
        connection.execute(text("INSERT INTO users (id,nome,email,senha_hash,role,ativo,created_at,updated_at) VALUES (1,'Teste','migration@example.com','unused','ADMIN',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO route_plans (id,revision,status,data,created_by,created_at,updated_at) VALUES (1,0,'RASCUNHO','{}',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
    command.upgrade(config, 'head')
    with isolated.connect() as connection:
        assert connection.execute(text('SELECT revision FROM route_plans WHERE id=1')).scalar() == 0
        assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar() == '20261104_0012'
        assert 'distributions' in inspect(connection).get_table_names()
    isolated.dispose()




def test_optimized_sequence_is_reflected_in_distribution(client, admin_headers, monkeypatch):
    url, work = create(client, admin_headers)
    second = note('n2', '101')
    second['destination']['latitude'] = -23.7
    data = body(work); data['notes'] = [note(), second]; data['routes'] = [route(ids=['n1', 'n2'])]
    work = put(client, admin_headers, url, data)
    monkeypatch.setattr(provider, 'matrix', lambda points: {'durations': [[0,10,1],[1,0,10],[1,1,0]], 'distances': [[0,10,1],[1,0,10],[1,1,0]]})
    monkeypatch.setattr(provider, 'geometry', fake_geometry)
    plan_url = f"/api/route-plans/{work['routes'][0]['plan_id']}"
    assert client.post(plan_url+'/calculate', headers=admin_headers, json={'revision': 0}).status_code == 200
    work = client.get(url, headers=admin_headers).json()
    assert work['routes'][0]['invoice_ids'] == ['n2', 'n1']
    assert client.post(plan_url+'/confirm', headers=admin_headers, json={'revision': 1}).status_code == 200
    work = client.get(url, headers=admin_headers).json()
    put(client, admin_headers, url, body(work))


def test_sankhya_permission_failure_does_not_expose_provider_secrets(monkeypatch):
    from app.services import sankhya
    from fastapi import HTTPException
    from pydantic import SecretStr
    monkeypatch.setattr(sankhya.settings, 'sankhya_client_id', 'test-client')
    monkeypatch.setattr(sankhya.settings, 'sankhya_client_secret', SecretStr('secret-not-for-output'))
    monkeypatch.setattr(sankhya.settings, 'sankhya_token', SecretStr('token-not-for-output'))
    monkeypatch.setattr(sankhya, '_post', lambda path, *args: {'access_token': 'private-token'} if path == '/authenticate' else {'status': '0', 'statusMessage': 'private-token'})
    with pytest.raises(HTTPException) as caught:
        sankhya.lookup_invoice('100')
    assert caught.value.status_code == 502
    assert 'DbExplorerSP.executeQuery' in caught.value.detail
    assert 'private-token' not in caught.value.detail
