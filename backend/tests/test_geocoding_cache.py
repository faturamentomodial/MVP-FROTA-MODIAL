from app.core.database import SessionLocal
from app.models.geocoding import GeocodedAddress
from app.services import route_planning as provider
from app.services.geocoding_cache import geocode
from app.services import dual_geocoding


def test_positive_street_match_is_shared_and_address_change_is_not_cached(monkeypatch):
    calls = []
    def lookup(db, address):
        calls.append(address)
        return {'schema_version': 2, 'candidates': [{'address': address, 'latitude': -23.4,
            'longitude': -46.5, 'street_found': True, 'house_number_found': False}]}
    monkeypatch.setattr(dual_geocoding, 'lookup', lookup)
    with SessionLocal() as db:
        result = geocode(db, 'Rua Carinas, Guarulhos, SP')
    with SessionLocal() as db:
        assert geocode(db, 'Rua Carinas, Guarulhos, SP') == result
        geocode(db, 'Rua Carinas, 76, Guarulhos, SP')
    assert len(calls) == 2
    assert result['candidates'][0]['house_number_found'] is False


def test_negative_results_are_cached_briefly_without_selecting_centroids(monkeypatch):
    with SessionLocal() as db:
        for result in ({'candidates': []}, {'candidates': [{'street_found': False}]}):
            address = 'Endereco sem rua ' + str(len(result['candidates']))
            monkeypatch.setattr(dual_geocoding, 'lookup', lambda db, address: result.copy())
            saved = geocode(db, address)
            assert saved['candidates'] == result['candidates']
            assert saved.get('selected') is None
            assert db.get(GeocodedAddress, address) is not None


def test_street_city_fallback_retains_number_before_approximation():
    variants = provider.geocoding_address_variants('Rua Carinas, 76 - Jardim Santa Inês, Guarulhos - SP - CEP 07141-310')
    assert 'Rua Carinas, 76, Guarulhos, SP' in variants
    assert variants[-1] == 'Rua Carinas, Guarulhos, SP'
    assert variants.index('Rua Carinas, 76, Guarulhos, SP') < len(variants) - 1
    assert not any(q == 'Guarulhos, SP' for q in variants)


def test_batch_rejects_other_municipality_and_city_centroids():
    from app.validate_pickup_addresses import street_matches
    result = {'candidates': [
        {'address': 'Rua Carinas, São Paulo, Brasil', 'street_found': True},
        {'address': 'Guarulhos, São Paulo, Brasil', 'street_found': False},
        {'address': 'Rua Carinas, Guarulhos, São Paulo, Brasil', 'street_found': True},
        {'address': 'Rua Outros Ramos, Guarulhos, Brasil', 'street_found': True}]}
    assert street_matches('Rua Carinas, 76 - Jardim Santa Inês, Guarulhos - SP', result) == [result['candidates'][2]]


def test_pickup_location_is_shared_but_not_reused_after_edit(client, admin_headers):
    address = 'Rua Carinas, 76, Guarulhos - SP'
    point = {'address': 'Rua Carinas, Guarulhos', 'latitude': -23.4, 'longitude': -46.5, 'street_found': True}
    data = {'nome': 'Coleta', 'telefone': '11999999999', 'endereco': address}
    pickup = client.post('/api/pickups', headers=admin_headers, json=data).json()
    with SessionLocal() as db:
        db.add(GeocodedAddress(address=address, result={'candidates': [point]}))
        db.commit()
    assert client.get('/api/pickups', headers=admin_headers).json()[0]['location'] == point
    response = client.put(f"/api/pickups/{pickup['id']}", headers=admin_headers, json={**data, 'endereco': 'Outro endereço'})
    assert response.status_code == 200
    assert client.get('/api/pickups', headers=admin_headers).json()[0]['location'] is None


def test_generic_and_numbered_streets_do_not_match_wrong_neighborhood_or_number():
    from app.services.geocoding_match import street_matches
    assert street_matches('Rua A, 68 - Ponte Alta, Guarulhos - SP', {'candidates': [
        {'address': 'Rua A, Vila Rio, Guarulhos, SP', 'street_found': True}]}) == []
    assert street_matches('Viela Projetada 3 - Recreio São Jorge, Guarulhos - SP', {'candidates': [
        {'address': 'Rua Projetada, Guarulhos, SP', 'street_found': True}]}) == []
