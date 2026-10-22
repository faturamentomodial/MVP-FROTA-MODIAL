"""Link unconfigured fleet vehicles by exact plate and verify real positions."""
import json
from collections import defaultdict

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Vehicle
from app.models.entities import VehicleTracking
from app.services.audit import audit
from app.services.tracking import provider, persist_positions


def plate_key(value):
    return ''.join(c for c in value.upper() if c.isalnum())


def configure(db, remote_vehicles, positions):
    by_plate = defaultdict(list)
    for row in remote_vehicles:
        by_plate[plate_key(row['licensePlate'])].append(str(row['id']))
    links = list(db.scalars(select(VehicleTracking)))
    linked = {link.vehicle_id: link for link in links}
    used = {link.tracker_id for link in links}
    created = 0
    unmatched = []
    for vehicle in db.scalars(select(Vehicle).where(Vehicle.ativo.is_(True))):
        if vehicle.id in linked:
            continue
        candidates = by_plate.get(plate_key(vehicle.placa), [])
        if len(candidates) != 1 or candidates[0] in used:
            unmatched.append(vehicle.placa)
            continue
        link = VehicleTracking(vehicle_id=vehicle.id, provider='POSITRON', tracker_id=candidates[0], active=True)
        db.add(link)
        links.append(link)
        used.add(link.tracker_id)
        audit(db, None, 'VINCULAR_RASTREADOR', 'VEHICLE', vehicle.id,
              {'source': 'positron_plate_match', 'tracker_id': link.tracker_id})
        created += 1
    db.flush()
    stored = persist_positions(db, positions, {link.tracker_id: link for link in links})
    return {'links_created': created, 'active_links': sum(link.active for link in links),
            'positions_received': len(positions), 'positions_stored': stored,
            'unmatched_plates': unmatched}


def main():
    # Fetch before writing: failed authentication never changes fleet links.
    vehicles, positions = provider.vehicles(), provider.positions()
    with SessionLocal() as db:
        result = configure(db, vehicles, positions)
        print(json.dumps(result))
        if not result['active_links'] or not positions:
            raise SystemExit('Tracking verification failed: no active links or provider positions.')
        from app.api.tracking import fleet
        response = fleet(db)
        located = [item['placa'] for item in response['items'] if item['position']]
        print(json.dumps({'provider_ready': response['provider_ready'], 'located_plates': located}))
        if not response['provider_ready'] or not located:
            raise SystemExit('Tracking verification failed: fleet has no usable positions.')


if __name__ == '__main__':
    main()
