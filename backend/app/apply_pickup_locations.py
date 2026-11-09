"""Apply an explicitly reviewed address file atomically, with backup and audit.

No geocoding, migrations, deploys or unrelated records are changed here.
Default is preview. --apply requires a new backup path.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Pickup
from app.models.geocoding import GeocodedAddress
from app.services.audit import audit


class Correction(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    id: int = Field(gt=0)
    name: str = Field(min_length=1)
    previous_address: str
    address: str = Field(min_length=5, max_length=500)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    precision: Literal['confirmed', 'street']
    provider: str
    source: str
    reason: str
    provider_result: dict = Field(default_factory=dict)


def prepare(db, records):
    if len({r.id for r in records}) != len(records):
        raise ValueError('Duplicate pickup IDs')
    backup, changes = [], []
    for record in records:
        pickup = db.scalar(select(Pickup).where(Pickup.id == record.id).with_for_update())
        if not pickup or pickup.nome != record.name:
            raise ValueError(f'Pickup identity changed: {record.id}')
        if pickup.endereco not in (record.previous_address, record.address):
            raise ValueError(f'Pickup address changed: {record.id}')
        cache = db.get(GeocodedAddress, record.address)
        previous = db.get(GeocodedAddress, pickup.endereco)
        manual = record.precision == 'confirmed'
        point = dict(address=record.address, latitude=record.latitude, longitude=record.longitude,
                     provider='manual' if manual else record.provider,
                     precision=record.precision, status='confirmed' if manual else 'approximate',
                     manual_confirmed=manual, house_number_found=manual,
                     source=record.source, review_reason=record.reason,
                     attribution='Geoapify | © OpenStreetMap contributors')
        # Never overwrite another human-confirmed coordinate, including the old key.
        for saved in (cache, previous):
            if saved and saved.result.get('manual_confirmed'):
                selected = saved.result.get('selected') or saved.result.get('candidates', [None])[0]
                if not manual or not selected or any(selected[k] != point[k] for k in ('latitude', 'longitude')):
                    raise ValueError(f'Conflicting manual confirmation: {record.id}')
        result = dict(schema_version=2, original_address=record.address, candidates=[point],
                      selected=point if manual else None, map_point=point, map_reviewed=True,
                      status=point['status'], precision=record.precision,
                      provider=point['provider'], manual_confirmed=manual,
                      selection_required=not manual, approximate=not manual,
                      verified_at=time.time(), expires_at=time.time() + 2592000,
                      review_source='user_corrected_addresses_2026_11_09',
                      reason=record.reason, provider_result=record.provider_result,
                      attribution=point['attribution'])
        if cache and cache.result.get('review_source') == result['review_source'] and all(
                cache.result.get('map_point', {}).get(k) == point[k] for k in point) and pickup.endereco == record.address:
            continue
        backup.append(dict(id=pickup.id, name=pickup.nome, address=pickup.endereco,
                           old_cache=deepcopy(previous.result) if previous else None,
                           target_address=record.address,
                           target_cache=deepcopy(cache.result) if cache else None))
        changes.append((pickup, cache, record, result))
    return backup, changes


def apply_changes(db, changes):
    for pickup, cache, record, result in changes:
        before = pickup.endereco
        pickup.endereco = record.address
        if cache:
            cache.result = result
        else:
            db.add(GeocodedAddress(address=record.address, result=result))
        audit(db, None, 'CORRIGIR_LOCALIZACAO', 'PICKUP', pickup.id,
              {'before_address': before, 'address': record.address,
               'latitude': record.latitude, 'longitude': record.longitude,
               'precision': record.precision, 'manual_confirmed': result['manual_confirmed'],
               'source': result['review_source'], 'evidence': record.source})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', required=True)
    parser.add_argument('--backup')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.apply and not args.backup:
        parser.error('--apply requires --backup')
    records = [Correction.model_validate(row) for row in json.loads(Path(args.file).read_text(encoding='utf-8'))]
    if not records:
        parser.error('Empty correction file')
    with SessionLocal() as db:
        backup, changes = prepare(db, records)
        if args.apply and changes:
            # Exclusive creation prevents accidentally overwriting the rollback evidence.
            with Path(args.backup).open('x', encoding='utf-8') as target:
                json.dump(backup, target, ensure_ascii=False, indent=2)
            apply_changes(db, changes)
            db.commit()
        print(json.dumps({'applied': args.apply, 'changed_ids': [r.id for _, _, r, _ in changes],
                          'locations': [{'id': r.id, 'address': r.address, 'precision': r.precision,
                                         'latitude': r.latitude, 'longitude': r.longitude} for r in records]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
