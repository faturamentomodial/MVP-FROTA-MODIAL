import time
import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
from app.services import dual_geocoding as geo
from app.services.geocoding_cache import geocode, confirm
from app.models.geocoding import GeocodedAddress

ADDRESS = 'Rua Arthur de Azevedo, 6 - Jardim Bela Vista, Guarulhos - SP'


def point(provider='nominatim', number='6', longitude=-46.5, **extra):
    return dict(address=ADDRESS, latitude=-23.4, longitude=longitude,
                street_found=True, house_number_found=bool(number), result_type='building',
                components={'street': 'Rua Arthur de Azevedo', 'number': number,
                            'city': 'Guarulhos', 'country_code': 'br', 'neighborhood': 'Jardim Bela Vista'},
                rank={'confidence': 1, 'confidence_street_level': 1,
                      'confidence_building_level': 1, 'match_type': 'full_match'}, **extra)


@pytest.fixture
def providers(monkeypatch):
    monkeypatch.setattr(geo.settings, 'geoapify_api_key', SecretStr('test-secret-never-return'))
    monkeypatch.setattr(geo.settings, 'geocoding_primary_enabled', True)
    monkeypatch.setattr(geo.settings, 'routes_geocoder_provider', 'nominatim')


def test_fallback_and_skip_secondary_when_primary_precise(monkeypatch, providers):
    calls = []
    monkeypatch.setattr(geo.route_planning, '_geocode_exact', lambda a: {'candidates': [point()]})
    monkeypatch.setattr(geo, 'geoapify', lambda a: calls.append(a) or {'candidates': [point()]})
    with SessionLocal() as db:
        assert geocode(db, ADDRESS)['provider'] == 'nominatim'
        assert not calls
        monkeypatch.setattr(geo.route_planning, '_geocode_exact', lambda a: {'candidates': []})
        # Different address and released quota for an independent user query.
        geo.cooldown(db, 'provider:nominatim', 0)
        second = ADDRESS.replace('6 -', '7 -')
        monkeypatch.setattr(geo, 'geoapify', lambda a: {'candidates': [point(number='7')]})
        assert geocode(db, second)['provider'] == 'geoapify'


def test_low_confidence_missing_score_wrong_number_and_centroids(providers):
    for change in ({'rank': {'confidence': .2}}, {'rank': {'confidence': 1, 'confidence_street_level': 1}},
                   {'result_type': 'city'}, {'result_type': 'suburb'}):
        p = {**point(), **change}
        result = geo.select_result(ADDRESS, [{'provider': 'geoapify', 'candidates': [p]}])
        assert result['selected'] is None
    assert geo.evaluate(ADDRESS, point(number='60'), 'nominatim')['precision'] == 'street'
    p = point(); p['components']['street'] = ''
    assert geo.select_result(ADDRESS, [{'provider': 'nominatim', 'candidates': [p]}])['precision'] == 'unverified'


def test_conflicting_providers_require_confirmation(providers):
    result = geo.select_result(ADDRESS, [
        {'provider': 'nominatim', 'candidates': [point(number='')]},
        {'provider': 'geoapify', 'candidates': [point(longitude=-46.6)]}])
    assert result['status'] == 'conflict' and result['selected'] is None
    assert len(result['candidates']) == 2


def test_rate_limit_shared_between_sessions_and_provider_cooldown(monkeypatch, providers):
    with SessionLocal() as db, Session(engine) as other:
        geo.reserve(db, 'provider:nominatim', 60)
        with pytest.raises(HTTPException) as caught:
            geo.reserve(other, 'provider:nominatim', 60)
        assert caught.value.status_code == 429
        monkeypatch.setattr(geo.route_planning, '_geocode_exact', lambda a: pytest.fail('quota must prevent calls'))
        monkeypatch.setattr(geo, 'geoapify', lambda a: {'candidates': [point()]})
        assert geo.lookup(other, ADDRESS)['provider'] == 'geoapify'


def test_outage_negative_cache_avoids_repeated_calls(monkeypatch, providers):
    calls = []
    def fail(a):
        calls.append(a)
        raise HTTPException(429, 'busy', headers={'Retry-After': '600'})
    monkeypatch.setattr(geo.route_planning, '_geocode_exact', fail)
    monkeypatch.setattr(geo, 'geoapify', fail)
    with SessionLocal() as db:
        first = geocode(db, ADDRESS)
        assert first['selected'] is None
        assert geocode(db, ADDRESS) == first
        assert len(calls) == 2
        assert 'test-secret-never-return' not in str(first)


def test_manual_confirmation_wins_and_address_edit_does_not_reuse(monkeypatch, providers):
    with SessionLocal() as db:
        result = confirm(db, ADDRESS, -23.42, -46.52, 1)
        db.commit()
        monkeypatch.setattr(geo, 'lookup', lambda *args: pytest.fail('must preserve manual'))
        assert geocode(db, ADDRESS) == result
        assert db.get(GeocodedAddress, ADDRESS + ' outro') is None


def test_concurrent_manual_confirmation_wins_over_automatic(monkeypatch, providers):
    with SessionLocal() as db:
        db.add(GeocodedAddress(address=ADDRESS, result={'candidates': []}))
        db.commit()
        def lookup(*args):
            with SessionLocal() as other:
                confirm(other, ADDRESS, -23.42, -46.52, 1)
                other.commit()
            return geo.select_result(ADDRESS, [{'provider': 'nominatim', 'candidates': [point()]}])
        monkeypatch.setattr(geo, 'lookup', lookup)
        result = geocode(db, ADDRESS)
        assert result['manual_confirmed'] is True
        assert result['selected']['latitude'] == -23.42


def test_confirmation_api_auth_validation_and_audit(client, admin_headers, driver_headers):
    payload = {'address': ADDRESS, 'latitude': -23.4, 'longitude': -46.5}
    assert client.post('/api/route-plans/geocode/confirm', headers=driver_headers, json=payload).status_code == 403
    assert client.post('/api/route-plans/geocode/confirm', headers=admin_headers,
                       json={**payload, 'latitude': 91}).status_code == 422
    response = client.post('/api/route-plans/geocode/confirm', headers=admin_headers, json=payload)
    assert response.status_code == 200, response.text
    assert client.get('/api/route-plans/geocode', headers=admin_headers,
                      params={'address': ADDRESS}).json()['manual_confirmed'] is True


def test_neighborhood_disagreement_requires_confirmation(providers):
    p = point()
    p['components']['neighborhood'] = 'Vila Gopouva'
    result = geo.select_result(ADDRESS, [{'provider': 'geoapify', 'candidates': [p]}])
    assert result['selected'] is None
    assert not result['candidates'][0]['neighborhood_matches']


def test_five_real_address_responses_remain_pending():
    import json
    from pathlib import Path
    rows = json.loads((Path(__file__).resolve().parents[2] / 'docs/geocoding-audit-2026-11-09.json').read_text(encoding='utf-8'))
    assert {row['id'] for row in rows} == {15, 34, 58, 77, 81}
    for row in rows:
        result = geo.select_result(row['address'], row['providers'])
        assert result['selected'] is None, row['id']
        assert result['selection_required']


def test_geoapify_transport_timeout_429_and_secret_redaction(monkeypatch, providers):
    from urllib.error import HTTPError
    calls = []
    def fail(request, timeout):
        calls.append(timeout)
        raise HTTPError(request.full_url, 429, 'secret in URL', {'Retry-After': '600'}, None)
    monkeypatch.setattr(geo, 'urlopen', fail)
    with pytest.raises(HTTPException) as caught:
        geo.geoapify(ADDRESS)
    assert caught.value.status_code == 429
    assert caught.value.headers['Retry-After'] == '600'
    assert 'test-secret-never-return' not in str(caught.value.detail)
    assert calls == [geo.settings.routes_timeout_seconds]
    monkeypatch.setattr(geo, 'urlopen', lambda *a, **kw: (_ for _ in ()).throw(TimeoutError('sensitive URL')))
    with pytest.raises(HTTPException) as caught:
        geo.geoapify(ADDRESS)
    assert caught.value.status_code == 503


def test_cooldown_blocks_other_addresses_without_repeating_failed_call(monkeypatch, providers):
    calls = []
    def fail(address):
        calls.append(address)
        raise HTTPException(503, 'down')
    monkeypatch.setattr(geo.route_planning, '_geocode_exact', fail)
    monkeypatch.setattr(geo, 'geoapify', fail)
    with SessionLocal() as db:
        geo.lookup(db, ADDRESS)
    with SessionLocal() as other:
        geo.lookup(other, ADDRESS + ' diferente')
    assert len(calls) == 2
