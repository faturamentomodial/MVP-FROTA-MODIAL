"""Explicit live validation against public Brazilian addresses; no database changes.

Run: python -m app.check_geoapify [--output ../docs/geoapify-validation.json]
This consumes Geoapify credits and never prints credentials or authenticated URLs.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from time import sleep

from fastapi import HTTPException
from app.core.config import settings
from app.services import geoapify, dual_geocoding

ADDRESSES = [
    'Rua Carinas, 76, Jardim Santa Inês, Guarulhos, SP',
    'Avenida Paulo Faccini, Macedo, Guarulhos, SP',
    'Rua Dom Pedro II, Centro, Guarulhos, SP',
    'Viela Projetada 3, Recreio São Jorge, Guarulhos, SP',
    'Rua A, 68, Ponte Alta, Guarulhos, SP',
    'Rua Arthur de Azevedo, 6, Jardim Bela Vista, Guarulhos, SP',
    "Rua Palmira D'Oeste, 5, Jardim Betel, Guarulhos, SP",
    'Avenida Josino Vieira de Goes, 275, Jardim Joamar, Guarulhos, SP',
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not settings.geoapify_api_key.get_secret_value():
        print('Configure GEOAPIFY_API_KEY no backend.')
        return 1
    report = {'checked_at': datetime.now(timezone.utc).isoformat(), 'provider': 'geoapify',
              'attribution': geoapify.ATTRIBUTION, 'addresses': [], 'route': None, 'matrix': None}
    route_points, failed = [], False
    for address in ADDRESSES:
        try:
            result = dual_geocoding.select_result(address, [geoapify.geocode(address)])
            report['addresses'].append({'query': address, **result})
            print(f"{address}: {result['status']}, {len(result['candidates'])} candidatos")
            eligible = [p for p in result['candidates'] if p['precision'] != 'unverified']
            # Explicit choices for transport testing only, never saved as user confirmations.
            if len(route_points) < 3 and eligible:
                route_points.append(eligible[0])
        except HTTPException as exc:
            failed = True
            report['addresses'].append({'query': address, 'error_status': exc.status_code})
            print(f'{address}: FALHA HTTP {exc.status_code}')
        sleep(max(settings.routes_min_interval_seconds, 1))
    if len(route_points) == 3:
        ordered = route_points + [route_points[0]]
        try:
            report['route'] = {'ordered_points': ordered, 'optimize_stops': False, **geoapify.geometry(ordered)}
            report['matrix'] = geoapify.matrix(route_points)
            print(f"Rota manual: {report['route']['distance']} metros, {report['route']['duration']} segundos")
            print('Matriz 3 x 3: OK')
        except HTTPException as exc:
            failed = True
            report['routing_error_status'] = exc.status_code
            print(f'Rotas/matriz: FALHA HTTP {exc.status_code}')
    else:
        failed = True
        print('Não há três candidatos elegíveis para validar o trajeto.')
    if args.output:
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
