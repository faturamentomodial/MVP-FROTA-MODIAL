import io
import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from app.core.database import SessionLocal
from app.models.geocoding import GeocodedAddress
from app.services import geoapify as geo, route_planning, dual_geocoding
from app.services.geocoding_cache import geocode, confirm

ADDRESS = 'Rua Carinas, 76, Jardim Santa Ines, Guarulhos, SP'
POINTS = [{'address': f'Rua Teste {i}, Guarulhos, SP', 'latitude': -23.45+i/10000, 'longitude': -46.53} for i in range(102)]


@pytest.fixture(autouse=True)
def geoapify_settings(monkeypatch):
    monkeypatch.setattr(geo.settings, 'geoapify_api_key', SecretStr('test-key-not-real'))
    monkeypatch.setattr(geo.settings, 'routes_geocoder_provider', 'geoapify')
    monkeypatch.setattr(geo.settings, 'routes_router_provider', 'geoapify')
    monkeypatch.setattr(geo.settings, 'routes_min_interval_seconds', 0)
    geo._last.clear()


def address_result(**extra):
    return {'formatted': ADDRESS, 'lat': -23.45, 'lon': -46.53, 'street': 'Rua Carinas', 'housenumber': '76',
            'suburb': 'Jardim Santa Ines', 'city': 'Guarulhos', 'country_code': 'br', 'result_type': 'building',
            'datasource': {'attribution': 'OpenStreetMap contributors'}, 'rank': {'match_type': 'full_match'}, **extra}


def route_response():
    return {'features': [{'geometry': {'type': 'MultiLineString', 'coordinates': [
        [[-46.53, -23.45], [-46.531, -23.451]], [[-46.531, -23.451], [-46.532, -23.452]]]},
        'properties': {'distance': 1234.5, 'time': 90.5}}]}


@pytest.mark.parametrize('row,precision', [(address_result(), 'building'),
    (address_result(rank={'match_type': 'interpolated'}), 'street'),
    (address_result(housenumber='760'), 'street'), (address_result(city='Sao Paulo'), 'unverified'),
    (address_result(result_type='suburb', street=''), 'unverified')])
def test_brazilian_address_selection_remains_conservative(monkeypatch, row, precision):
    monkeypatch.setattr(geo, 'request', lambda *args, **kwargs: {'results': [row]})
    result = geo.geocode(ADDRESS)
    selected = dual_geocoding.select_result(ADDRESS, [result])
    assert selected['candidates'][0]['precision'] == precision
    assert bool(selected['selected']) == (precision == 'building')
    assert 'Geoapify' in selected['attribution']
    assert result['candidates'][0]['datasource'] == row['datasource']


@pytest.mark.parametrize('data', [{'results': None}, {'results': [address_result(lat=float('nan'))]}, {'results': [address_result(lon=181)]}, {}])
def test_invalid_geocoding_is_rejected(monkeypatch, data):
    monkeypatch.setattr(geo, 'request', lambda *args, **kwargs: data)
    with pytest.raises(HTTPException) as error: geo.geocode(ADDRESS)
    assert error.value.status_code == 503


def test_address_not_found_keeps_empty_candidates(monkeypatch):
    monkeypatch.setattr(geo, 'request', lambda *args, **kwargs: {'results': []})
    result = geo.geocode(ADDRESS)
    assert result['candidates'] == [] and result['selection_required']


def test_route_order_units_multiline_and_large_routes(monkeypatch):
    calls = []
    def fetch(path, params):
        assert path == 'routing'
        assert params['optimize_stops'] == 'false'
        calls.append(params['waypoints'].split('|'))
        return route_response()
    monkeypatch.setattr(geo, 'request', fetch)
    result = route_planning.geometry(POINTS)
    flattened = calls[0] + [p for chunk in calls[1:] for p in chunk[1:]]
    assert flattened == [f"{p['latitude']},{p['longitude']}" for p in POINTS]
    assert all(len(chunk) <= 20 for chunk in calls)
    assert result['distance'] == len(calls) * 1234.5
    assert result['duration'] == len(calls) * 90.5
    assert result['geometry']['type'] == 'LineString'
    assert result['geometry']['coordinates'][:3] == [[-46.53, -23.45], [-46.531, -23.451], [-46.532, -23.452]]


@pytest.mark.parametrize('data', [{'features': []}, {'features': [{'geometry': {'type': 'Polygon', 'coordinates': []}}]},
    {'features': [{'geometry': {'type': 'LineString', 'coordinates': [[181, 0], [0, 0]]}, 'properties': {'distance': -1, 'time': 2}}]}])
def test_invalid_or_missing_route_does_not_fabricate_estimates(monkeypatch, data):
    monkeypatch.setattr(geo, 'request', lambda *args, **kwargs: data)
    with pytest.raises(HTTPException) as error: geo.geometry(POINTS[:2])
    assert error.value.status_code == 422


def test_matrix_chunking_indices_and_internal_contract(monkeypatch):
    calls = []
    def fetch(path, body):
        calls.append(body)
        assert path == 'routematrix' and len(body['sources']) * len(body['targets']) <= 1000
        return {'sources_to_targets': [[{'source_index': i, 'target_index': j, 'distance': i*100+j, 'time': i*10+j}
                for j in reversed(range(len(body['targets'])))] for i in range(len(body['sources']))]}
    monkeypatch.setattr(geo, 'request', fetch)
    result = route_planning.matrix(POINTS[:32])
    assert len(calls) == 4
    assert calls[0]['sources'][0]['location'] == [POINTS[0]['longitude'], POINTS[0]['latitude']]
    assert result['code'] == 'Ok'
    assert len(result['durations']) == 32 and len(result['distances'][0]) == 32
    assert result['distances'][2][3] == 203


@pytest.mark.parametrize('rows', [[], [[None]], [[{'source_index': 0, 'target_index': 0, 'distance': None, 'time': None}]],
    [[{'source_index': 1, 'target_index': 0, 'distance': 1, 'time': 1}]]])
def test_incomplete_or_unreachable_matrix_is_rejected(monkeypatch, rows):
    monkeypatch.setattr(geo, 'request', lambda *args, **kwargs: {'sources_to_targets': rows})
    with pytest.raises(HTTPException) as error: geo.matrix(POINTS[:1])
    assert error.value.status_code == 422


@pytest.mark.parametrize('failure,code', [(HTTPError('secret-url', 429, 'secret', {'Retry-After': '12'}, None), 429),
    (HTTPError('secret-url', 403, 'secret', {}, None), 503), (HTTPError('secret-url', 400, 'secret', {}, None), 422),
    (HTTPError('secret-url', 500, 'secret', {}, None), 503), (URLError('secret'), 503)])
def test_transport_errors_redact_key_and_preserve_rate_limit(monkeypatch, failure, code, caplog):
    def fail(*args, **kwargs): raise failure
    monkeypatch.setattr(geo, 'urlopen', fail)
    with pytest.raises(HTTPException) as error: geo.geocode(ADDRESS)
    assert error.value.status_code == code
    assert 'secret' not in error.value.detail and 'test-key-not-real' not in caplog.text
    if code == 429: assert error.value.headers['Retry-After'] == '12'


def test_request_country_filter_and_missing_key(monkeypatch):
    calls = []
    def fetch(req, timeout):
        calls.append(req)
        return io.BytesIO(b'{"results":[]}')
    monkeypatch.setattr(geo, 'urlopen', fetch)
    geo.geocode(ADDRESS)
    query = parse_qs(urlsplit(calls[0].full_url).query)
    assert query['filter'] == ['countrycode:br'] and query['lang'] == ['pt']
    assert query['apiKey'] == ['test-key-not-real']
    monkeypatch.setattr(geo.settings, 'geoapify_api_key', SecretStr(''))
    with pytest.raises(HTTPException) as error: geo.geocode(ADDRESS)
    assert error.value.status_code == 503 and len(calls) == 1


def test_local_rate_limit_and_invalid_json(monkeypatch):
    monkeypatch.setattr(geo, 'urlopen', lambda *args, **kwargs: io.BytesIO(b'not-json'))
    with pytest.raises(HTTPException) as error: geo.geocode(ADDRESS)
    assert error.value.status_code == 503
    monkeypatch.setattr(geo.settings, 'routes_min_interval_seconds', 60)
    with pytest.raises(HTTPException) as error: geo.geocode(ADDRESS)
    assert error.value.status_code == 429


def test_cache_invalidation_reuse_and_manual_coordinates(monkeypatch):
    calls = []
    monkeypatch.setattr(geo, 'request', lambda *args, **kwargs: calls.append(args) or {'results': [address_result()]})
    with SessionLocal() as db:
        db.add(GeocodedAddress(address=ADDRESS, result={'schema_version': 2, 'expires_at': time.time()+1000,
            'cache_provider': 'nominatim', 'candidates': [], 'selected': None}))
        db.commit()
        result = geocode(db, ADDRESS)
        assert result['cache_provider'] == 'geoapify' and result['selected']['provider'] == 'geoapify'
        assert geocode(db, ADDRESS) == result and len(calls) == 1
        confirmed = confirm(db, 'Local confirmado', -23.45, -46.53, 1)
        assert geocode(db, 'Local confirmado') == confirmed and len(calls) == 1


@pytest.mark.parametrize('template', [False, True])
def test_manual_delivery_order_through_api(monkeypatch, client, admin_headers, template):
    def fetch(path, params=None, body=None):
        if path == 'routing':
            assert params['waypoints'] == '|'.join(f"{p['latitude']},{p['longitude']}" for p in [POINTS[0], POINTS[2], POINTS[1], POINTS[0]])
            assert params['optimize_stops'] == 'false'
            return route_response()
        size = len(body['sources'])
        return {'sources_to_targets': [[{'source_index': i, 'target_index': j, 'distance': 100, 'time': 20}
                for j in range(size)] for i in range(size)]}
    monkeypatch.setattr(geo, 'request', fetch)
    base = '/api/route-templates' if template else '/api/route-plans'
    payload = {'name': 'Ordem manual Geoapify', 'origin': POINTS[0], 'invoices': [
        {'number': 'NF2', 'volumes': 1, 'destination': POINTS[2]}, {'number': 'NF1', 'volumes': 1, 'destination': POINTS[1]}]}
    if not template: payload['vehicle_id'] = 1
    plan = client.post(base, headers=admin_headers, json=payload).json()
    response = client.post(f"{base}/{plan['id']}/calculate", headers=admin_headers, json={'revision': plan['revision'], 'optimize': False})
    assert response.status_code == 200, response.text
    result = response.json()
    assert [s['address'] for s in result['stops']] == [POINTS[2]['address'], POINTS[1]['address']]
    assert result['result']['provider'] == 'geoapify' and result['result']['algorithm'] == 'manual'
