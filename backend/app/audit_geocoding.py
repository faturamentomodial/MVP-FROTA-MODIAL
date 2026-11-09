"""Explicit five-address audit using files and an isolated in-memory quota DB."""
import argparse
import csv
import json
import time
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.models.geocoding import GeocodingQuota
from app.services import dual_geocoding as geo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--live', action='store_true', help='One full-address query per provider per address; no production DB access.')
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise SystemExit('Report already exists. Reuse it; choose a new path only for a deliberate new audit.')
    if not args.live:
        raise SystemExit('Use --live for this explicit, limited audit.')
    engine = create_engine('sqlite+pysqlite:///:memory:')
    GeocodingQuota.__table__.create(engine)
    report = []
    with Path(args.input).open(encoding='utf-8-sig', newline='') as source, Session(engine) as db:
        for row in csv.DictReader(source, delimiter=';'):
            if row['ID'] not in {'15', '34', '58', '77', '81'}:
                continue
            address = row['Endereco cadastrado']
            results, errors = [], []
            for provider in (geo.settings.routes_geocoder_provider, 'geoapify'):
                try:
                    geo.reserve(db, 'provider:' + provider, max(1.1, geo.settings.routes_min_interval_seconds,
                                geo.settings.geoapify_min_interval_seconds))
                    result = geo.geoapify(address) if provider == 'geoapify' else geo.route_planning._geocode_exact(address)
                    results.append({**result, 'provider': provider})
                except HTTPException as exc:
                    errors.append({'provider': provider, 'status': exc.status_code})
            entry = {'id': int(row['ID']), 'address': address, 'queried_at': time.time(),
                     'providers': results, 'decision': geo.select_result(address, results, errors),
                     'policy': {'require_neighborhood_match': geo.settings.geocoding_require_neighborhood_match,
                                'confidence': geo.settings.geocoding_min_confidence,
                                'street_confidence': geo.settings.geocoding_min_street_confidence,
                                'building_confidence': geo.settings.geocoding_min_building_confidence,
                                'conflict_meters': geo.settings.geocoding_conflict_meters}}
            report.append(entry)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f"ID {row['ID']}: {entry['decision']['status']}", flush=True)
            time.sleep(max(1.2, geo.settings.routes_min_interval_seconds, geo.settings.geoapify_min_interval_seconds))


if __name__ == '__main__':
    main()
