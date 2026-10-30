from fastapi import HTTPException
from app.services import route_planning as provider
from app.models.route_plans import RoutePlan
from app.core.database import SessionLocal


def payload():
    point = lambda i: {'address': f'Rua Teste {i}, São Paulo SP', 'latitude': -23.5+i/1000, 'longitude': -46.6}
    return {'name':'Dez notas', 'vehicle_id':1, 'origin':point(0), 'profile':'truck', 'invoices':[{'number':str(i), 'volumes':i+1, 'destination':point(max(1,i))} for i in range(10)]}


def fake_matrix(points):
    n=len(points)
    return {'code':'Ok', 'durations':[[abs(i-j)*10 for j in range(n)] for i in range(n)], 'distances':[[abs(i-j)*100 for j in range(n)] for i in range(n)]}


def fake_geometry(points):
    return {'geometry':{'type':'LineString','coordinates':[[p['longitude'],p['latitude']] for p in points]}, 'distance':900, 'duration':90}


def test_ten_notes_persistence_manual_conflict_confirmation(client, admin_headers, driver_headers, monkeypatch):
    monkeypatch.setattr(provider,'matrix',fake_matrix)
    monkeypatch.setattr(provider,'geometry',fake_geometry)
    assert client.get('/api/route-plans').status_code==401
    assert client.get('/api/route-plans',headers=driver_headers).status_code==403
    p=client.post('/api/route-plans',json=payload(),headers=admin_headers).json()
    url=f"/api/route-plans/{p['id']}"
    calc=client.post(url+'/calculate',json={'revision':0},headers=admin_headers)
    assert calc.status_code==200,calc.text
    p=calc.json()
    assert len(p['invoices'])==10 and len(p['stops'])==9
    assert p['result']['truck_restrictions_supported'] is False
    assert p['result']['return_to_origin'] is True
    line = p['result']['geometry']['coordinates']
    assert line[0] == line[-1]
    assert len(line) == len(p['stops']) + 2
    assert client.post(url+'/calculate',json={'revision':0},headers=admin_headers).status_code==409
    with SessionLocal() as db:
        assert db.get(RoutePlan,p['id']).data['result']['distance']==900
    body=payload();body['revision']=1;body['invoices'].reverse()
    edited=client.put(url,json=body,headers=admin_headers)
    assert edited.status_code==200
    assert edited.json()['result'] is None
    assert client.put(url,json=body,headers=admin_headers).status_code==409
    assert client.post(url+'/confirm',json={'revision':2},headers=admin_headers).status_code==422
    manual=client.post(url+'/calculate',json={'revision':2,'optimize':False},headers=admin_headers).json()
    assert manual['invoices'][0]['number']=='9'
    assert manual['result']['geometry']['coordinates'][0] == manual['result']['geometry']['coordinates'][-1]
    confirmed=client.post(url+'/confirm',json={'revision':3},headers=admin_headers)
    assert confirmed.json()['status']=='CONFIRMADO'
    assert client.put(url,json={**body,'revision':4},headers=admin_headers).status_code==409
    assert len(client.get(url+'/versions',headers=admin_headers).json())==5


def test_provider_failure_atomicity_and_geocoding(client,admin_headers,monkeypatch):
    monkeypatch.setattr(provider.settings, 'routes_geocoder_provider', 'photon')
    monkeypatch.setattr(provider.settings, 'routes_geocoder_url', 'https://photon.komoot.io')
    p=client.post('/api/route-plans',json=payload(),headers=admin_headers).json()
    original_matrix = provider.matrix
    def unavailable(*args): raise HTTPException(503,'Provedor indisponível')
    monkeypatch.setattr(provider,'matrix',unavailable)
    url=f"/api/route-plans/{p['id']}"
    assert client.post(url+'/calculate',json={'revision':0},headers=admin_headers).status_code==503
    assert client.get(url,headers=admin_headers).json()['revision']==0
    monkeypatch.setattr(provider,'request',lambda *a:{'features':[]})
    assert client.get('/api/route-plans/geocode?address=Rua+inexistente',headers=admin_headers).json()['candidates']==[]
    monkeypatch.setattr(provider,'request',lambda *a:{'features':[{'geometry':{'coordinates':[-46,-23]},'properties':{'name':'Rua A'}},{'geometry':{'coordinates':[-47,-24]},'properties':{'name':'Rua B'}}]})
    assert len(client.get('/api/route-plans/geocode?address=Rua+ambigua',headers=admin_headers).json()['candidates'])==2
    monkeypatch.setattr(provider, 'matrix', original_matrix)
    monkeypatch.setattr(provider,'request',lambda *a:{'code':'Ok','durations':[[None]],'distances':[[1]]})
    assert client.post(url+'/calculate',json={'revision':0},headers=admin_headers).status_code==422


def test_exact_asymmetric_round_trip():
    assert provider.optimal_order([[0,10,1],[1,0,10],[1,1,0]])==[2,1]


def test_invalid_notes(client,admin_headers):
    body=payload();body['invoices'][1]['number']='0'
    assert client.post('/api/route-plans',json=body,headers=admin_headers).status_code==422


def test_timeout_and_local_quota(monkeypatch):
    import pytest
    monkeypatch.setattr(provider.settings,'routes_geocoder_url','https://example.invalid')
    monkeypatch.setattr(provider.settings,'routes_min_interval_seconds',1)
    provider._last.clear()
    def timeout(*a,**kw): raise TimeoutError()
    monkeypatch.setattr(provider,'urlopen',timeout)
    with pytest.raises(HTTPException) as caught:
        provider.geocode('Rua Teste 123')
    assert caught.value.status_code==503
    with pytest.raises(HTTPException) as caught:
        provider.geocode('Outro endereço 456')
    assert caught.value.status_code==429


def test_aditive_migration_roundtrip():
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, inspect, text
    spec=importlib.util.spec_from_file_location('route_migration',Path('migrations/versions/20261028_0008_route_plans.py'))
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    engine=create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY)'))
        migration.op=Operations(MigrationContext.configure(connection))
        migration.upgrade()
        assert 'route_plans' in inspect(connection).get_table_names()
        migration.downgrade()
        assert inspect(connection).get_table_names()==['users']


def test_assigned_plan_creates_trip_with_cargo_once(client, admin_headers, driver_headers, monkeypatch):
    monkeypatch.setattr(provider, 'matrix', fake_matrix)
    monkeypatch.setattr(provider, 'geometry', fake_geometry)
    body = {**payload(), 'driver_id': 1}
    invalid = client.post('/api/route-plans', json={**body, 'driver_id': 999}, headers=admin_headers)
    assert invalid.status_code == 422
    plan = client.post('/api/route-plans', json=body, headers=admin_headers).json()
    url = f"/api/route-plans/{plan['id']}"
    assert client.get('/api/trips/planned', headers=driver_headers).json() == []
    calculated = client.post(url+'/calculate', json={'revision': 0}, headers=admin_headers).json()
    assert client.post(url+'/confirm', json={'revision': calculated['revision']}, headers=admin_headers).status_code == 200
    assigned = client.get('/api/trips/planned', headers=driver_headers).json()
    assert [p['id'] for p in assigned] == [plan['id']]
    trip = client.post('/api/trips', json={'route_plan_id': plan['id'], 'vehicle_id': 1, 'km_inicial': 1000}, headers=driver_headers)
    assert trip.status_code == 201, trip.text
    data = trip.json()
    assert [n['numero_nota'] for n in data['notas']] == [n['number'] for n in calculated['invoices']]
    assert data['total_volumes'] == 55
    cargo_url = f"/api/trips/{data['id']}/cargo"
    assert client.put(cargo_url, headers=driver_headers, json={
        'notas': [{'numero_nota': 'ALTERADA', 'volumes': 1}]
    }).status_code == 403
    assert client.put(f"/api/trips/{data['id']}/delivery-order", headers=driver_headers, json={
        'invoice_ids': [n['id'] for n in reversed(data['notas'])], 'revision': data['delivery_revision']
    }).status_code == 403
    assert client.get(f"/api/trips/{data['id']}", headers=driver_headers).json()['notas'] == data['notas']
    assert data['route_plan']['origin'] == calculated['origin']
    assert all(data['route_plan']['origin'][key] == value for key, value in body['origin'].items())
    assert client.get('/api/trips/planned', headers=driver_headers).json() == []
    assert client.post('/api/trips', json={'route_plan_id': plan['id'], 'vehicle_id': 1, 'km_inicial': 1000}, headers=driver_headers).status_code == 409
    assert client.post(f"/api/trips/{data['id']}/start", headers=driver_headers).status_code == 400


def test_unassigned_plan_cannot_be_used_by_driver(client, admin_headers, driver_headers):
    plan = client.post('/api/route-plans', json=payload(), headers=admin_headers).json()
    response = client.post('/api/trips', json={'route_plan_id': plan['id'], 'vehicle_id': 1, 'km_inicial': 1000}, headers=driver_headers)
    assert response.status_code == 403


def test_other_driver_plan_is_hidden_and_forbidden(client, admin_headers, driver_headers, monkeypatch):
    from app.models import Driver, User
    from app.models.enums import UserRole
    with SessionLocal() as db:
        other = Driver(nome='Outro motorista', user=User(nome='Outro', email='other@example.com', senha_hash='unused', role=UserRole.MOTORISTA))
        db.add(other)
        db.commit()
        other_id = other.id
    monkeypatch.setattr(provider, 'matrix', fake_matrix)
    monkeypatch.setattr(provider, 'geometry', fake_geometry)
    plan = client.post('/api/route-plans', json={**payload(), 'driver_id': other_id}, headers=admin_headers).json()
    url = f"/api/route-plans/{plan['id']}"
    client.post(url+'/calculate', json={'revision': 0}, headers=admin_headers)
    assert client.post(url+'/confirm', json={'revision': 1}, headers=admin_headers).status_code == 200
    assert client.get('/api/trips/planned', headers=driver_headers).json() == []
    assert client.get(url, headers=driver_headers).status_code == 403
    assert client.post('/api/trips', json={'route_plan_id': plan['id'], 'vehicle_id': 1, 'km_inicial': 1000}, headers=driver_headers).status_code == 403


def test_driver_cannot_create_unplanned_trip(client, driver_headers):
    response = client.post('/api/trips', headers=driver_headers, json={'vehicle_id': 1, 'km_inicial': 1000})
    assert response.status_code == 403
    assert client.get('/api/trips/current', headers=driver_headers).json() is None
    assert client.get('/api/vehicles?available=true', headers=driver_headers).json()['total'] == 1


def test_round_trip_order_accounts_for_return_cost():
    # Open path would choose 1 then 2 (cost 2), but its return costs 100.
    cost = [[0, 1, 2], [1, 0, 1], [100, 2, 0]]
    assert provider.optimal_order(cost) == [2, 1]


def test_nominatim_geocoding_quality_and_errors(monkeypatch):
    import pytest
    monkeypatch.setattr(provider.settings, 'routes_geocoder_provider', 'nominatim')
    def response(base, path):
        assert 'countrycodes=br' in path and 'addressdetails=1' in path
        return [{'display_name': 'Rua A, Brasil', 'lat': '-23', 'lon': '-46', 'address': {}}]
    monkeypatch.setattr(provider, 'request', response)
    provider._nominatim_geocode.cache_clear()
    result = provider.geocode('Rua A 123')
    assert result['provider'] == 'nominatim' and result['selection_required']
    assert result['candidates'][0]['house_number_found'] is False
    provider._nominatim_geocode.cache_clear()
    monkeypatch.setattr(provider, 'request', lambda *args: [])
    assert provider.geocode('Rua A 123')['candidates'] == []
    for invalid in [{'error': 'bad'}, [{'lat': 'NaN', 'lon': '0'}]]:
        provider._nominatim_geocode.cache_clear()
        monkeypatch.setattr(provider, 'request', lambda *args: invalid)
        with pytest.raises(HTTPException) as caught:
            provider.geocode('Rua A 123')
        assert caught.value.status_code == 503


def test_nominatim_cep_uses_postal_search_and_shared_cache(monkeypatch):
    monkeypatch.setattr(provider.settings, 'routes_geocoder_provider', 'nominatim')
    monkeypatch.setattr(provider.settings, 'routes_geocoder_url', 'https://nominatim.openstreetmap.org')
    calls = []
    def response(base, path):
        calls.append(path)
        assert 'postalcode=04744-040' in path and 'q=' not in path
        return []
    monkeypatch.setattr(provider, 'request', response)
    provider._nominatim_geocode.cache_clear()
    assert provider.geocode('04744040')['candidates'] == []
    assert provider.geocode('04744-040')['candidates'] == []
    assert len(calls) == 1
    provider._nominatim_geocode.cache_clear()


def test_provider_http_errors_explain_failure(monkeypatch):
    import pytest
    from urllib.error import HTTPError
    monkeypatch.setattr(provider.settings, 'routes_min_interval_seconds', 0)
    for status in (403, 404, 429, 502):
        def fail(*args, **kwargs):
            raise HTTPError('https://example.invalid', status, 'failure', {}, None)
        monkeypatch.setattr(provider, 'urlopen', fail)
        with pytest.raises(HTTPException) as caught:
            provider.request('https://example.invalid', '/search')
        assert caught.value.status_code == (429 if status == 429 else 503)
        assert str(status) in caught.value.detail or status == 429


def test_geocoder_rejects_mismatched_public_endpoint(monkeypatch):
    import pytest
    monkeypatch.setattr(provider.settings, 'routes_geocoder_provider', 'nominatim')
    monkeypatch.setattr(provider.settings, 'routes_geocoder_url', 'https://photon.komoot.io')
    with pytest.raises(HTTPException) as caught:
        provider.geocode('04744040')
    assert 'incompatível' in caught.value.detail
