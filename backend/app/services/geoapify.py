"""Geoapify adapters; meters, seconds and GeoJSON longitude/latitude internally."""
import json
import math
from threading import Lock
from time import monotonic, sleep
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException
from app.core.config import settings

_lock = Lock()
_last = {}
ATTRIBUTION = 'Geoapify | © OpenStreetMap contributors'


def request(path, params=None, body=None):
    key = settings.geoapify_api_key.get_secret_value()
    if not key:
        raise HTTPException(503, 'Configure GEOAPIFY_API_KEY no backend.')
    with _lock:
        now = monotonic()
        if now - _last.get(path, -100) < settings.routes_min_interval_seconds:
            raise HTTPException(429, 'Limite local do Geoapify. Aguarde e tente novamente.', headers={'Retry-After': '1'})
        _last[path] = now
    url = 'https://api.geoapify.com/v1/' + path + '?' + urlencode({**(params or {}), 'apiKey': key})
    headers = {'Accept': 'application/json', 'User-Agent': 'Modial-RoutePlanning/1.0'}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    try:
        req = Request(url, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        with urlopen(req, timeout=settings.routes_timeout_seconds) as response:
            raw = response.read(5_000_001)
        if len(raw) > 5_000_000:
            raise ValueError()
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError()
        if data.get('statusCode', 200) >= 400:
            fail(data['statusCode'])
        return data
    except HTTPError as exc:
        retry = exc.headers.get('Retry-After', '60') if exc.headers else '60'
        fail(exc.code, retry)
    except (OSError, ValueError, TypeError):
        # The URL and provider exceptions contain apiKey; never log or propagate them.
        raise HTTPException(503, 'Geoapify indisponível ou resposta inválida.') from None


def fail(status, retry='60'):
    if status == 429:
        raise HTTPException(429, 'Geoapify excedeu o limite de uso. Aguarde e tente novamente.',
                            headers={'Retry-After': retry if retry.isdigit() else '60'}) from None
    if status in (400, 404, 422):
        raise HTTPException(422, 'Geoapify não encontrou percurso ou recebeu parâmetros inválidos. Revise os destinos.') from None
    raise HTTPException(503, 'Geoapify indisponível ou acesso recusado. Verifique a chave e as permissões.') from None


def valid_number(value, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or (nonnegative and value < 0):
        raise ValueError()
    return value


def coordinate(lon, lat):
    valid_number(lon); valid_number(lat)
    if abs(lon) > 180 or abs(lat) > 90:
        raise ValueError()
    return [lon, lat]


def geocode(address):
    data = request('geocode/search', {'text': address, 'filter': 'countrycode:br', 'lang': 'pt', 'format': 'json', 'limit': 5})
    try:
        rows = data['results']
        if not isinstance(rows, list):
            raise ValueError()
        candidates = []
        for row in rows[:5]:
            lon, lat = coordinate(row['lon'], row['lat'])
            street, number = row.get('street', ''), row.get('housenumber', '')
            kind = row.get('result_type', 'unknown')
            # Interpolation and partial matches must not become automatic building matches.
            exact = row.get('rank', {}).get('match_type') in ('full_match', 'match_by_building')
            candidates.append(dict(address=row['formatted'], latitude=lat, longitude=lon,
                components=dict(street=street, number=str(number), city=row.get('city') or row.get('town') or row.get('municipality', ''),
                                neighborhood=row.get('suburb') or row.get('district') or row.get('quarter', ''), country_code=row.get('country_code', '')),
                street_found=bool(street), house_number_found=bool(number),
                result_type='building' if kind == 'building' and exact else 'road' if kind == 'building' else kind,
                provider='geoapify', datasource=row.get('datasource', {}), attribution=ATTRIBUTION,
                place_id=row.get('place_id'), rank=row.get('rank', {})))
        return dict(candidates=candidates, provider='geoapify', selection_required=True, attribution=ATTRIBUTION)
    except (KeyError, TypeError, ValueError, AttributeError):
        raise HTTPException(503, 'Resposta de geocodificação Geoapify inválida.') from None


def geometry(points):
    if len(points) < 2:
        raise HTTPException(422, 'Informe origem e destino.')
    coordinates, distance, duration = [], 0, 0
    # Bound URL size, sharing endpoints without altering the visit order.
    for start in range(0, len(points) - 1, 19):
        chunk = points[start:start+20]
        if start:
            sleep(settings.routes_min_interval_seconds)
        try:
            for point in chunk:
                coordinate(point['longitude'], point['latitude'])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(422, 'Coordenadas inválidas.') from None
        data = request('routing', {'waypoints': '|'.join(f"{p['latitude']},{p['longitude']}" for p in chunk),
            'mode': 'drive', 'units': 'metric', 'format': 'geojson', 'traffic': 'free_flow',
            'optimize_stops': 'false', 'intermediate_waypoint_mode': 'stopover'})
        try:
            route = data['features'][0]
            geometry = route['geometry']
            if geometry['type'] == 'MultiLineString':
                lines = geometry['coordinates']
            elif geometry['type'] == 'LineString':
                lines = [geometry['coordinates']]
            else:
                raise ValueError()
            if not lines:
                raise ValueError()
            for line in lines:
                if len(line) < 2:
                    raise ValueError()
                segment = [coordinate(*p) for p in line]
                coordinates.extend(segment[1:] if coordinates and coordinates[-1] == segment[0] else segment)
            distance += valid_number(route['properties']['distance'], nonnegative=True)
            duration += valid_number(route['properties']['time'], nonnegative=True)
        except (KeyError, IndexError, TypeError, ValueError):
            raise HTTPException(422, 'Percurso Geoapify indisponível ou resposta inválida para os destinos.') from None
    return {'geometry': {'type': 'LineString', 'coordinates': coordinates}, 'distance': distance, 'duration': duration}


def matrix(points):
    size = len(points)
    durations, distances = [[None] * size for _ in points], [[None] * size for _ in points]
    for origin in range(0, size, 31):
        for destination in range(0, size, 31):
            if origin or destination:
                sleep(settings.routes_min_interval_seconds)
            sources, targets = points[origin:origin+31], points[destination:destination+31]
            try:
                body = {'mode': 'drive', 'units': 'metric', 'traffic': 'free_flow',
                    'sources': [{'location': coordinate(p['longitude'], p['latitude'])} for p in sources],
                    'targets': [{'location': coordinate(p['longitude'], p['latitude'])} for p in targets]}
            except (KeyError, TypeError, ValueError):
                raise HTTPException(422, 'Coordenadas inválidas.') from None
            data = request('routematrix', body=body)
            try:
                rows = data['sources_to_targets']
                if len(rows) != len(sources) or any(len(row) != len(targets) for row in rows):
                    raise ValueError()
                seen = set()
                for row in rows:
                    for cell in row:
                        i, j = cell['source_index'], cell['target_index']
                        if type(i) is not int or type(j) is not int or not 0 <= i < len(sources) or not 0 <= j < len(targets) or (i, j) in seen:
                            raise ValueError()
                        seen.add((i, j))
                        durations[origin+i][destination+j] = valid_number(cell['time'], nonnegative=True)
                        distances[origin+i][destination+j] = valid_number(cell['distance'], nonnegative=True)
            except (KeyError, TypeError, ValueError):
                raise HTTPException(422, 'Matriz Geoapify incompleta ou destino inacessível.') from None
    return {'code': 'Ok', 'durations': durations, 'distances': distances}
