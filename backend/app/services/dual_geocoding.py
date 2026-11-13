"""Conservative geocoding selection and shared quotas for the configured provider."""
import math
import re
import time
from urllib.parse import urlsplit

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
                attribution='Geoapify | © OpenStreetMap contributors' if settings.routes_geocoder_provider == 'geoapify' else '© OpenStreetMap contributors', schema_version=2)


def lookup(db, address):
    results, errors = [], []
    primary = settings.routes_geocoder_provider
    providers = [primary] if settings.geocoding_primary_enabled else []
    for name in providers:
        bucket = 'provider:' + name
        try:
            interval = max(
                settings.routes_min_interval_seconds,
                1.1 if name == 'nominatim' and urlsplit(settings.routes_geocoder_url).hostname == 'nominatim.openstreetmap.org' else 0)
            def fetch(query):
                reserve(db, bucket, interval)
                return route_planning._geocode_exact(query)
            result = route_planning.geocode(address, fetch=fetch)
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
