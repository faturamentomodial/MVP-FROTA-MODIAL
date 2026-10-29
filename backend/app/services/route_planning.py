"""Real Nominatim/Photon geocoding and OSRM routing adapters."""
import json
import math
from functools import lru_cache
from threading import Lock
from time import monotonic
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from fastapi import HTTPException
from app.core.config import settings

_lock = Lock()
_last = {}


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
        raise HTTPException(429 if exc.code == 429 else 503, "Provedor excedeu o limite de uso." if exc.code == 429 else "Provedor indisponível.") from exc
    except (OSError, ValueError) as exc:
        raise HTTPException(503, "Provedor indisponível ou resposta inválida; nenhum resultado estimado foi utilizado.") from exc


def geocode(address):
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
                candidates.append({'address': label or address, 'latitude': lat, 'longitude': lon})
        return {'candidates': candidates, 'selection_required': True, 'provider': 'photon'}
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(503, 'Resposta de geocodificação inválida.') from exc


def nominatim_geocode(address):
    return _nominatim_geocode(' '.join(address.split()), settings.routes_geocoder_url, int(monotonic() // 86400))


@lru_cache(maxsize=256)
def _nominatim_geocode(address, base, cache_period):
    data = request(base, '/search?' + urlencode({
        'q': address, 'format': 'jsonv2', 'addressdetails': 1, 'countrycodes': 'br',
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
                               'house_number_found': bool(details.get('house_number'))})
        return {'candidates': candidates, 'selection_required': True, 'provider': 'nominatim',
                'attribution': 'OpenStreetMap contributors'}
    except (KeyError, TypeError, ValueError) as exc:
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
