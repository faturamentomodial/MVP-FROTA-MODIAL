from app.services import route_planning as provider


def test_pickup_address_expands_abbreviations_preserving_context(monkeypatch):
    monkeypatch.setattr(provider.settings, 'routes_geocoder_provider', 'nominatim')
    calls = []

    def lookup(address, base, period):
        calls.append(address)
        return {'candidates': []}

    monkeypatch.setattr(provider, '_nominatim_geocode', lookup)
    monkeypatch.setattr(provider, 'sleep', lambda _: None)
    provider.geocode('Rua Maria de Fatima Kida, 306 - Vila Nossa Sra. de Fatima')
    assert calls == ['Rua Maria de Fatima Kida, 306, Vila Nossa Senhora de Fatima', 'Rua Maria de Fatima Kida, Vila Nossa Senhora de Fatima', 'Maria de Fatima Kida, Vila Nossa Senhora de Fatima']


def test_normalization_keeps_postcode_house_number_and_city():
    assert provider.normalize_geocoding_address('  Av. Brasil, 123 - Jd. Europa - Guarulhos SP, 07191-290 ') == (
        'Avenida Brasil, 123, Jardim Europa, Guarulhos SP, 07191-290'
    )
    assert provider.normalize_geocoding_address('04744-040') == '04744-040'
    assert provider.normalize_geocoding_address('Rua Sraiva, 12-A') == 'Rua Sraiva, 12-A'


def test_street_fallback_preserves_city_and_street_numbers():
    variants = provider.geocoding_address_variants('Av. Brasil, 123, apto 42 - Jd. Europa - Guarulhos SP')
    assert 'Avenida Brasil, Jardim Europa, Guarulhos SP' in variants
    assert all('Guarulhos SP' in query for query in variants)
    assert 'Rua 25 de Marco, Sao Paulo' in provider.geocoding_address_variants('Rua 25 de Marco, 100, Sao Paulo')
    assert '25' in provider.geocoding_address_variants('Rua 25, Goiania')[-1]


def test_fallback_returns_street_but_rejects_city_centroid(monkeypatch):
    calls = []
    waits = []
    monkeypatch.setattr(provider, 'sleep', waits.append)

    def lookup(query):
        calls.append(query)
        candidates = [] if len(calls) == 1 else [
            {'address': 'City', 'street_found': False},
            {'address': 'Rua Brasil, Guarulhos', 'street_found': True, 'house_number_found': False},
        ]
        return {'candidates': candidates, 'selection_required': True}

    monkeypatch.setattr(provider, '_geocode_exact', lookup)
    result = provider.geocode('Rua Brasil, 123, Guarulhos')
    assert calls == ['Rua Brasil, 123, Guarulhos', 'Rua Brasil, Guarulhos']
    assert len(result['candidates']) == 1
    assert result['candidates'][0]['street_found']
    assert result['approximate'] is True
    assert waits and waits[0] >= 1


def test_provider_outage_does_not_trigger_broader_search(monkeypatch):
    import pytest
    from fastapi import HTTPException
    calls = []

    def fail(query):
        calls.append(query)
        raise HTTPException(503, 'Unavailable')

    monkeypatch.setattr(provider, '_geocode_exact', fail)
    with pytest.raises(HTTPException):
        provider.geocode('Rua Brasil, 123, Guarulhos')
    assert len(calls) == 1
