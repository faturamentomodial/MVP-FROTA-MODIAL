"""Conservative geocoding: one full-address request per provider, no retries."""
import json
import math
import re
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.geocoding import GeocodingQuota
from app.services import route_planning
from app.services.geocoding_match import plain, street_name


def reserve(db, key, seconds):
    """Compare-and-swap on the shared DB; never sleep holding a worker."""
    now = time.time()
    with Session(bind=db.get_bind()) as quota:
        changed = quota.execute(update(GeocodingQuota).where(
            GeocodingQuota.key == key, GeocodingQuota.available_at <= now
        ).values(available_at=now + seconds)).rowcount
        if changed:
            quota.commit()
            return
        if quota.get(GeocodingQuota, key):
            raise HTTPException(429, 'Consulta em espera; tente novamente mais tarde.')
        quota.add(GeocodingQuota(key=key, available_at=now + seconds))
        try:
            quota.commit()
        except IntegrityError:
            quota.rollback()
            raise HTTPException(429, 'Consulta em espera; tente novamente mais tarde.') from None


def cooldown(db, key, seconds):
    with Session(bind=db.get_bind()) as quota:
        quota.execute(update(GeocodingQuota).where(GeocodingQuota.key == key).values(
            available_at=time.time() + seconds))
        quota.commit()


def geoapify(address):
    key = settings.geoapify_api_key.get_secret_value()
    if not key:
        raise HTTPException(503, 'Geoapify não configurado no backend.')
    path = 'https://api.geoapify.com/v1/geocode/search?' + urlencode({
        'text': address, 'filter': 'countrycode:br', 'lang': 'pt',
        'format': 'json', 'limit': 5, 'apiKey': key})
    try:
        with urlopen(Request(path, headers={'User-Agent': 'Modial-RoutePlanning/1.0'}),
                     timeout=settings.routes_timeout_seconds) as response:
            data = json.loads(response.read(5_000_001))
        candidates = []
        for row in data['results'][:5]:
            lat, lon = float(row['lat']), float(row['lon'])
            if not math.isfinite(lat) or not math.isfinite(lon) or abs(lat) > 90 or abs(lon) > 180:
                raise ValueError()
            candidates.append({
                'address': row.get('formatted', address), 'latitude': lat, 'longitude': lon,
                'provider': 'geoapify', 'result_type': row.get('result_type'),
                'rank': {k: row.get('rank', {}).get(k) for k in (
                    'confidence', 'confidence_street_level', 'confidence_building_level', 'match_type')},
                'components': {'street': row.get('street', ''), 'number': row.get('housenumber', ''),
                    'city': row.get('city', ''), 'neighborhood': row.get('suburb', ''),
                    'country_code': row.get('country_code', '')},
                'street_found': bool(row.get('street')),
                'house_number_found': bool(row.get('housenumber')),
                'datasource': row.get('datasource', {}),
                'attribution': 'Geoapify | © OpenStreetMap contributors',
            })
        return {'provider': 'geoapify', 'candidates': candidates}
    except HTTPError as exc:
        # Never log the URL or exception: both contain the credential.
        retry_after = exc.headers.get('Retry-After', '') if exc.headers else ''
        headers = {'Retry-After': retry_after} if retry_after.isdigit() else None
        raise HTTPException(429 if exc.code == 429 else 503,
                            'Geoapify temporariamente indisponível.', headers=headers) from None
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(503, 'Resposta Geoapify indisponível ou inválida.') from None


def expected(address):
    normalized = route_planning.normalize_geocoding_address(address)
    parts = [p.strip() for p in normalized.split(',')]
    city = re.search(r',\s*([^,]+?)(?:,\s*|\s+)[A-Z]{2}(?:\s*,|\s*$)', normalized)
    number = re.match(r'^(\d+[A-Za-z]?(?:-\d+)?)\b', parts[1]) if len(parts) > 1 else None
    before_city = normalized[:city.start()].split(',') if city else []
    neighborhood_parts = before_city[2:] if number else before_city[1:]
    neighborhood = plain(neighborhood_parts[-1].strip()) if neighborhood_parts else ''
    return street_name(parts[0]), plain(city[1].strip()) if city else '', number[1].lower() if number else '', neighborhood


def evaluate(address, candidate, provider):
    street, city, number, neighborhood = expected(address)
    p = {**candidate, 'provider': provider}
    c = p.get('components', {})
    if not isinstance(c, dict):
        c = {}
    c = {k: v if isinstance(v, str) else '' for k, v in c.items()}
    # Old cache entries without structured components are suggestions only.
    match = bool(city and c.get('street') and street == street_name(c['street'])
                 and city == plain(c.get('city', '')) and c.get('country_code', '').lower() == 'br')
    if p.get('result_type') in ('city', 'suburb', 'district', 'county', 'state', 'country', 'postcode', 'municipality', 'administrative'):
        match = False
    # Single-letter streets are ambiguous without matching neighborhood evidence.
    if len(street) < 3:
        actual_neighborhood = plain(c.get('neighborhood', ''))
        match = match and bool(actual_neighborhood and neighborhood == actual_neighborhood)
    precise = match and bool(number and number == str(c.get('number', '')).lower())
    neighborhood_matches = not neighborhood or neighborhood == plain(c.get('neighborhood', ''))
    if settings.geocoding_require_neighborhood_match and not neighborhood_matches:
        precise = False
    if provider == 'geoapify':
        rank = p.get('rank', {})
        def score(name, threshold):
            value = rank.get(name)
            return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and threshold <= value <= 1
        precise = precise and p.get('result_type') == 'building' and rank.get('match_type') in (
            'full_match', 'match_by_building') and score('confidence', settings.geocoding_min_confidence) and score(
            'confidence_street_level', settings.geocoding_min_street_confidence) and score(
            'confidence_building_level', settings.geocoding_min_building_confidence)
    else:
        precise = precise and p.get('result_type') in ('house', 'building', 'residential', 'commercial')
    p.update(precision='building' if precise else 'street' if match else 'unverified',
             status='automatic' if precise else 'approximate' if match else 'needs_confirmation',
             manual_confirmed=False, neighborhood_matches=neighborhood_matches)
    return p


def distance(a, b):
    lat1, lat2 = math.radians(a['latitude']), math.radians(b['latitude'])
    dlat, dlon = lat2 - lat1, math.radians(b['longitude'] - a['longitude'])
    return 6371000 * 2 * math.asin(min(1, math.sqrt(
        math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)))


def select_result(address, results, errors=None):
    candidates = [evaluate(address, p, r['provider']) for r in results for p in r.get('candidates', [])]
    eligible = [p for p in candidates if p['precision'] != 'unverified']
    conflict = any(distance(a, b) > settings.geocoding_conflict_meters
                   for i, a in enumerate(eligible) for b in eligible[i+1:])
    exact = [p for p in eligible if p['precision'] == 'building']
    selected = exact[0] if exact and not conflict else None
    status = 'conflict' if conflict else 'automatic' if selected else 'approximate' if eligible else 'needs_confirmation'
    return dict(candidates=candidates, selected=selected, selection_required=selected is None,
                provider=selected['provider'] if selected else None, status=status,
                precision='building' if selected else 'street' if eligible else 'unverified',
                approximate=selected is None, original_address=address, manual_confirmed=False,
                verified_at=time.time(), errors=errors or [],
                attribution='Geoapify | © OpenStreetMap contributors', schema_version=2)


def lookup(db, address):
    results, errors = [], []
    primary = settings.routes_geocoder_provider
    providers = [primary] if settings.geocoding_primary_enabled else []
    providers.append('geoapify')
    for name in providers:
        if name == 'geoapify' and not settings.geoapify_api_key.get_secret_value():
            errors.append({'provider': name, 'status': 'not_configured'})
            continue
        bucket = 'provider:' + name
        try:
            interval = settings.geoapify_min_interval_seconds if name == 'geoapify' else max(
                settings.routes_min_interval_seconds,
                1.1 if urlsplit(settings.routes_geocoder_url).hostname == 'nominatim.openstreetmap.org' else 0)
            reserve(db, bucket, interval)
            result = geoapify(address) if name == 'geoapify' else route_planning._geocode_exact(address)
            results.append({**result, 'provider': name})
        except HTTPException as exc:
            seconds = settings.geocoding_failure_cache_seconds
            retry = (exc.headers or {}).get('Retry-After', '')
            if retry.isdigit():
                seconds = max(seconds, int(retry))
            # Local quota denial does not extend the reservation indefinitely.
            if exc.status_code != 429 or exc.detail != 'Consulta em espera; tente novamente mais tarde.':
                cooldown(db, bucket, seconds)
            errors.append({'provider': name, 'status': exc.status_code})
        current = select_result(address, results, errors)
        if current['selected']:
            return current
    return select_result(address, results, errors)
