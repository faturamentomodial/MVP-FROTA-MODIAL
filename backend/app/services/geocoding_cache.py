"""Persistent results and short negative cache; manual confirmation never expires."""
import hashlib
import time
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.models.geocoding import GeocodedAddress
from app.services import dual_geocoding
from app.core.config import settings


def geocode(db, address):
    address = address.strip()
    cached = db.get(GeocodedAddress, address)
    if cached and (cached.result.get('manual_confirmed') or
                   cached.result.get('schema_version') == 2 and cached.result.get('expires_at', 0) > time.time()):
        return cached.result
    lease = 'address:' + hashlib.sha256(address.encode()).hexdigest()
    dual_geocoding.reserve(db, lease, settings.routes_timeout_seconds * 2 + 10)
    try:
        db.expire_all()
        cached = db.get(GeocodedAddress, address)
        if cached and cached.result.get('manual_confirmed'):
            return cached.result
        result = dual_geocoding.lookup(db, address)
        ttl = settings.geocoding_cache_seconds if result.get('candidates') and not result.get('errors') else settings.geocoding_failure_cache_seconds
        result['expires_at'] = time.time() + ttl
        if cached:
            # A concurrent manual confirmation always wins over this lookup.
            db.execute(update(GeocodedAddress).where(GeocodedAddress.address == address,
                GeocodedAddress.result['manual_confirmed'].as_boolean().is_not(True)
            ).values(result=result), execution_options={'synchronize_session': False})
        else:
            db.add(GeocodedAddress(address=address, result=result))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
        db.expire_all()
        saved = db.get(GeocodedAddress, address)
        return saved.result if saved else result
    finally:
        dual_geocoding.cooldown(db, lease, 0)


def confirm(db, address, latitude, longitude, user_id):
    address = address.strip()
    point = dict(address=address, latitude=latitude, longitude=longitude,
                 provider='manual', precision='confirmed', status='confirmed', manual_confirmed=True)
    result = dict(original_address=address, candidates=[point], selected=point,
                  provider='manual', precision='confirmed', status='confirmed', manual_confirmed=True,
                  confirmed_by=user_id, verified_at=time.time(), selection_required=False,
                  approximate=False, schema_version=2,
                  attribution='Geoapify | © OpenStreetMap contributors')
    row = db.get(GeocodedAddress, address)
    if row:
        result['suggestions'] = row.result.get('suggestions', row.result.get('candidates', []))
        row.result = result
    else:
        db.add(GeocodedAddress(address=address, result=result))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Localização alterada por outra consulta. Confirme novamente.') from None
    return result
