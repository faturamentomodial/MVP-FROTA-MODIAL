"""Real Photon/OSRM adapters. No synthetic routing fallback."""
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
        if now - _last.get(bucket, -100) < settings.routes_min_interval_seconds:
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
    """Held-Karp: exact open path from origin, no return, <=10 stops."""
    n = len(cost) - 1
    @lru_cache(None)
    def solve(current, remaining):
        if not remaining:
            return 0, ()
        return min((cost[current][j] + solve(j, remaining ^ (1 << (j-1)))[0], (j,) + solve(j, remaining ^ (1 << (j-1)))[1]) for j in range(1, n+1) if remaining & (1 << (j-1)))
    return list(solve(0, (1 << n)-1)[1])
