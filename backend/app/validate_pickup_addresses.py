"""Run: python -m app.validate_pickup_addresses --report /tmp/pickups.json.

Only street matches in the explicitly supplied city are persisted. No coordinates
are invented for missing addresses. Re-running reuses positive database matches.
"""
import argparse
import json
import time
from pathlib import Path

from sqlalchemy import select
from app.core.database import SessionLocal
from app.models import Pickup
from app.models.geocoding import GeocodedAddress
from app.services import route_planning as provider
from app.services.geocoding_match import street_matches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True)
    parser.add_argument('--previous')
    parser.add_argument('--fallback-photon', action='store_true')
    args = parser.parse_args()
    from urllib.parse import urlsplit
    if urlsplit(provider.settings.routes_geocoder_url).hostname == 'nominatim.openstreetmap.org':
        parser.error('Validação em massa desabilitada no Nominatim público. Use instância própria/contratada ou app.audit_geocoding para os cinco casos explícitos.')
    previous = {}
    if args.previous:
        previous = {p['endereco']: p.get('result', {}) for p in json.loads(Path(args.previous).read_text())}
    report = []
    with SessionLocal() as db:
        items = db.scalars(select(Pickup).order_by(Pickup.id)).all()
        for item in items:
            entry = dict(id=item.id, nome=item.nome, endereco=item.endereco, ativo=item.ativo)
            try:
                cached = db.get(GeocodedAddress, item.endereco)
                if cached and cached.result.get('manual_confirmed'):
                    entry.update(status='confirmado_manualmente', result=cached.result)
                    report.append(entry)
                    continue
                result = cached.result if cached else previous.get(item.endereco, {})
                candidates = street_matches(item.endereco, result)
                if not candidates:
                    queries = provider.geocoding_address_variants(item.endereco)
                    # The initial full-address audit has already tried the longer
                    # variants. Query the new street + municipality forms only.
                    if item.endereco in previous and not previous[item.endereco].get('candidates'):
                        queries = queries[-2:]
                    for query in queries:
                        time.sleep(max(1.2, provider.settings.routes_min_interval_seconds))
                        result = provider._geocode_exact(query)
                        candidates = street_matches(item.endereco, result)
                        if candidates:
                            result.update(query_used=query, approximate=not candidates[0].get('house_number_found'))
                            break
                if not candidates and args.fallback_photon:
                    old_provider, old_url = provider.settings.routes_geocoder_provider, provider.settings.routes_geocoder_url
                    try:
                        provider.settings.routes_geocoder_provider = 'photon'
                        provider.settings.routes_geocoder_url = 'https://photon.komoot.io'
                        query = provider.geocoding_address_variants(item.endereco)[-1]
                        time.sleep(1.2)
                        alternative = provider._geocode_exact(query)
                        candidates = street_matches(item.endereco, alternative)
                        if candidates:
                            result = {**alternative, 'query_used': query, 'approximate': not candidates[0].get('house_number_found')}
                    finally:
                        provider.settings.routes_geocoder_provider, provider.settings.routes_geocoder_url = old_provider, old_url
                if candidates:
                    result = {**result, 'candidates': candidates}
                    if cached:
                        cached.result = result
                    else:
                        db.add(GeocodedAddress(address=item.endereco, result=result))
                    db.commit()
                    entry.update(status='numero_localizado' if candidates[0].get('house_number_found') else 'rua_aproximada', result=result)
                else:
                    if cached:
                        db.delete(cached)
                        db.commit()
                    entry.update(status='nao_localizado', result=result)
            except Exception as exc:
                db.rollback()
                entry.update(status='erro', error=getattr(exc, 'detail', str(exc)))
            report.append(entry)
            Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({k: entry[k] for k in ('id', 'nome', 'status')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
