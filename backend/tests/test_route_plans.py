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
    confirmed=client.post(url+'/confirm',json={'revision':3},headers=admin_headers)
    assert confirmed.json()['status']=='CONFIRMADO'
    assert client.put(url,json={**body,'revision':4},headers=admin_headers).status_code==409
    assert len(client.get(url+'/versions',headers=admin_headers).json())==5


def test_provider_failure_atomicity_and_geocoding(client,admin_headers,monkeypatch):
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


def test_exact_asymmetric_open_path():
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
