"""Real Nominatim/Photon geocoding and OSRM routing adapters."""
import json
import logging
import math
import re
from functools import lru_cache
from threading import Lock
from time import monotonic, sleep
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from fastapi import HTTPException
from app.core.config import settings

_lock = Lock()
_last = {}
logger = logging.getLogger(__name__)


def request(base, path):
    if not base:
        raise HTTPException(503, "Provedor não configurado. Configure ROUTES_GEOCODER_URL e ROUTES_ROUTER_URL.")
    bucket = base + path.split('?')[0].split('/v1/')[0]
    with _lock:
        now = monotonic()
        interval = max(settings.routes_min_interval_seconds, 1 if 'nominatim.openstreetmap.org' in base else 0)
        if now - _last.get(bucket, -100) < interval:
            raise HTTPException(429, "Limite local do provedor. Aguarde e tente novamente.")
        _last[bucket] = now
    try:
        with urlopen(Request(base.rstrip('/') + path, headers={'User-Agent': 'Modial-RoutePlanning/1.0', 'Accept': 'application/json'}), timeout=settings.routes_timeout_seconds) as response:
            return json.loads(response.read(5_000_001))
    except HTTPError as exc:
        logger.warning('Route provider HTTP failure: base=%s status=%s', base, exc.code)
        detail = {
            403: 'Provedor de mapas recusou o acesso (HTTP 403). Verifique o bloqueio do IP do servidor e a configuração do provedor.',
            404: 'Endpoint do provedor não encontrado (HTTP 404). Confira ROUTES_GEOCODER_PROVIDER, ROUTES_GEOCODER_URL e ROUTES_ROUTER_URL.',
            429: 'Provedor excedeu o limite de uso. Aguarde e tente novamente.',
        }.get(exc.code, f'Provedor de mapas indisponível (HTTP {exc.code}). Tente novamente mais tarde.')
        raise HTTPException(429 if exc.code == 429 else 503, detail) from exc
    except (OSError, ValueError) as exc:
        logger.warning('Route provider connection or JSON failure: base=%s error=%s', base, type(exc).__name__)
        raise HTTPException(503, "Provedor indisponível ou resposta inválida; nenhum resultado estimado foi utilizado.") from exc


def geocode(address):
    variants = geocoding_address_variants(address)
    for index, query in enumerate(variants):
        if index:
            # Additional attempts share the same provider quota as the first one.
            sleep(max(settings.routes_min_interval_seconds, 1.1))
        result = _geocode_exact(query)
        if index:
            # A neighborhood or city centroid is not a street location.
            result = {**result, 'candidates': [p for p in result['candidates'] if p.get('street_found')]}
        if result['candidates']:
            return {**result, 'query_used': query, 'approximate': index > 0 or any(
                not p.get('house_number_found', False) for p in result['candidates'])}
    return result


def _geocode_exact(address):
    # A previous Photon configuration may remain when switching to Nominatim.
    host = urlsplit(settings.routes_geocoder_url).hostname or ''
    if ((settings.routes_geocoder_provider == 'nominatim' and host == 'photon.komoot.io')
            or (settings.routes_geocoder_provider == 'photon' and host == 'nominatim.openstreetmap.org')):
        raise HTTPException(503, 'Configuração de geocodificação incompatível. Ajuste ROUTES_GEOCODER_PROVIDER e ROUTES_GEOCODER_URL para o mesmo serviço e reinicie o backend.')
    if settings.routes_geocoder_provider == 'nominatim':
        return nominatim_geocode(address)
    try:
        rows = request(settings.routes_geocoder_url, '/api/?' + urlencode({'q': address, 'limit': 5}))['features']
        candidates = []
        for row in rows:
            lon, lat = row['geometry']['coordinates'][:2]
            props = row['properties']
            label = ', '.join(str(props[k]) for k in ('name', 'street', 'housenumber', 'postcode', 'city', 'state', 'country') if props.get(k))
            if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
                candidates.append({'address': label or address, 'latitude': lat, 'longitude': lon,
                                   'street_found': bool(props.get('street') or props.get('osm_key') == 'highway'),
                                   'house_number_found': bool(props.get('housenumber'))})
        return {'candidates': candidates, 'selection_required': True, 'provider': 'photon'}
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(503, 'Resposta de geocodificação inválida.') from exc


def normalize_geocoding_address(address):
    address = ' '.join(address.split())
    # Expand common Brazilian abbreviations without dropping neighborhood/city.
    for abbreviation, expanded in (
        ('sra', 'Senhora'), ('sr', 'Senhor'), ('nsa', 'Nossa'),
        ('ns', 'Nossa Senhora'), ('jd', 'Jardim'), ('vl', 'Vila'),
        ('sta', 'Santa'), ('sto', 'Santo'), ('dr', 'Doutor'), ('dra', 'Doutora'),
        ('prof', 'Professor'), ('profa', 'Professora'), ('pres', 'Presidente'),
        ('eng', 'Engenheiro'), ('dep', 'Deputado'), ('ver', 'Vereador'),
        ('pca', 'Praca'), ('tv', 'Travessa'), ('trav', 'Travessa'),
        ('rod', 'Rodovia'), ('estr', 'Estrada'), ('pq', 'Parque'),
        ('res', 'Residencial'), ('cj', 'Conjunto'), ('av', 'Avenida'), ('r', 'Rua'),
    ):
        address = re.sub(r'(?<!\w)' + abbreviation + r'\.?(?!\w)', expanded, address, flags=re.IGNORECASE)
    address = re.sub(r'\s+[-\u2013\u2014]\s+', ', ', address)
    return address


def geocoding_address_variants(address):
    normalized = normalize_geocoding_address(address)
    # Remove delivery instructions and unit details, retaining geographic context.
    clean = re.sub(r'\([^)]*\)', '', normalized)
    clean = re.sub(
        r'(?<!\w)(?:apto?|apartamento|bloco|bl|sala|fundos|complemento|referencia|referência)\b\.?[^,]*',
        '', clean, flags=re.IGNORECASE,
    )
    clean = ', '.join(part.strip(' ,') for part in clean.split(',') if part.strip(' ,'))
    # Only strip numbers after a comma or at the end of the street component.
    # Street names such as "Rua 25 de Marco" must retain their numbers.
    street_only = re.sub(r',\s*(?:(?:n[º°o]?\.?|numero)\s*)?\d+[A-Za-z]?(?:-[A-Za-z])?(?=\s*(?:,|$))', '', clean, flags=re.IGNORECASE)
    street_only = re.sub(r'^((?:\S+\s+)+\S*[^\W\d_])\s+\d+[A-Za-z]?(?=,|$)', r'\1', street_only)
    without_type = re.sub(r'^(?:Rua|Avenida|Travessa|Praca|Praça|Estrada|Rodovia)\s+', '', street_only, flags=re.IGNORECASE)
    # A neighborhood or stale postcode can prevent a valid street from matching.
    # Keep the explicit municipality and state; never fall back to a city alone.
    locality = re.search(r',\s*([^,]+),\s*([A-Z]{2})(?:\s*,|\s*$)', clean)
    simplified = []
    if locality:
        street = clean.split(',')[0].strip()
        number = re.match(r'^\s*(\d+[A-Za-z]?)\b', clean.split(',')[1]) if ',' in clean else None
        city_state = f'{locality[1].strip()}, {locality[2]}'
        if number:
            simplified.append(f'{street}, {number[1]}, {city_state}')
        simplified.append(f'{street}, {city_state}')
    return list(dict.fromkeys(q for q in (normalized, clean, street_only, without_type, *simplified) if len(q) >= 5))


def nominatim_geocode(address):
    address = normalize_geocoding_address(address)
    if re.fullmatch(r'\d{5}-?\d{3}', address):
        digits = address.replace('-', '')
        address = digits[:5] + '-' + digits[5:]
    return _nominatim_geocode(address, settings.routes_geocoder_url, int(monotonic() // 86400))


@lru_cache(maxsize=256)
def _nominatim_geocode(address, base, cache_period):
    data = request(base, '/search?' + urlencode({
        ('postalcode' if re.fullmatch(r'\d{5}-\d{3}', address) else 'q'): address,
        'format': 'jsonv2', 'addressdetails': 1, 'countrycodes': 'br',
        'accept-language': 'pt-BR', 'limit': 5, 'dedupe': 1,
    }))
    try:
        if not isinstance(data, list):
            raise ValueError()
        candidates = []
        for row in data[:5]:
            lat, lon = float(row['lat']), float(row['lon'])
            if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise ValueError()
            details = row.get('address', {})
            candidates.append({'address': row['display_name'], 'latitude': lat, 'longitude': lon,
                               'components': {'street': details.get('road', ''),
                                              'city': details.get('city') or details.get('town') or details.get('municipality', ''),
                                              'number': details.get('house_number', ''),
                                              'neighborhood': details.get('suburb') or details.get('neighbourhood', ''),
                                              'country_code': details.get('country_code', '')},
                               'result_type': row.get('addresstype', row.get('type', '')),
                               'house_number_found': bool(details.get('house_number')),
                               'street_found': bool(details.get('road') or row.get('class') == 'highway' or row.get('category') == 'highway')})
        return {'candidates': candidates, 'selection_required': True, 'provider': 'nominatim',
                'attribution': 'OpenStreetMap contributors'}
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(503, 'Resposta de geocodifica\u00e7\u00e3o Nominatim inv\u00e1lida.') from exc


def coordinates(points):
    return ';'.join(f"{p['longitude']},{p['latitude']}" for p in points)


def matrix(points):
    data = request(settings.routes_router_url, '/table/v1/driving/' + coordinates(points) + '?annotations=duration,distance')
    try:
        if data['code'] != 'Ok':
            raise ValueError()
        for key in ('durations', 'distances'):
            rows = data[key]
            if len(rows) != len(points) or any(len(r) != len(points) for r in rows):
                raise ValueError()
            if any(v is None or not math.isfinite(v) or v < 0 for r in rows for v in r):
                raise ValueError()
        return data
    except (KeyError, TypeError, ValueError):
        raise HTTPException(422, 'Matriz viária incompleta ou destino inacessível. Revise os endereços.')


def geometry(points):
    data = request(settings.routes_router_url, '/route/v1/driving/' + coordinates(points) + '?overview=full&geometries=geojson&steps=false')
    try:
        route = data['routes'][0]
        if data['code'] != 'Ok' or route['geometry']['type'] != 'LineString' or len(route['geometry']['coordinates']) < 2:
            raise ValueError()
        for lon, lat in route['geometry']['coordinates']:
            if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise ValueError()
        return {'geometry': route['geometry'], 'distance': route['distance'], 'duration': route['duration']}
    except (KeyError, IndexError, TypeError, ValueError):
        raise HTTPException(422, 'Percurso viário indisponível para os destinos.')


def optimal_order(cost):
    """Held-Karp: exact circuit from and back to origin, <=10 stops."""
    n = len(cost) - 1
    @lru_cache(None)
    def solve(current, remaining):
        if not remaining:
            return cost[current][0], ()
        return min((cost[current][j] + solve(j, remaining ^ (1 << (j-1)))[0], (j,) + solve(j, remaining ^ (1 << (j-1)))[1]) for j in range(1, n+1) if remaining & (1 << (j-1)))
    return list(solve(0, (1 << n)-1)[1])
