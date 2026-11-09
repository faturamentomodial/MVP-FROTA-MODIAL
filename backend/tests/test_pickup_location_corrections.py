import json
from pathlib import Path
import pytest
from sqlalchemy import select
from app.core.database import SessionLocal
from app.models import Pickup, AuditLog
from app.models.geocoding import GeocodedAddress
from app.apply_pickup_locations import Correction, prepare, apply_changes
from app.services.pickup_locations import location_for_map


def records():
    path = Path(__file__).resolve().parents[2] / 'docs/coletas-localizacoes-aplicar-2026-11-09.json'
    return [Correction.model_validate(row) for row in json.loads(path.read_text(encoding='utf-8'))]


def seed(db):
    for r in records():
        db.add(Pickup(id=r.id, nome=r.name, endereco=r.previous_address,
                      telefone='11999999999', ativo=True, tipo='COSTUREIRA'))
    db.add(Pickup(id=81, nome='MERCIA', endereco='Manter endereco', telefone='11999999999'))
    db.commit()


def test_four_corrections_visible_on_map_without_automatic_route_selection(client, admin_headers):
    with SessionLocal() as db:
        seed(db)
        backup, changes = prepare(db, records())
        assert len(backup) == len(changes) == 4
        assert db.get(Pickup, 58).endereco == records()[1].previous_address
        apply_changes(db, changes)
        db.commit()
        assert db.get(Pickup, 81).endereco == 'Manter endereco'
        for r in records():
            p = db.get(Pickup, r.id)
            cached = db.get(GeocodedAddress, r.address).result
            assert p.endereco == r.address and p.telefone == '11999999999' and p.ativo
            assert location_for_map(cached)['latitude'] == r.latitude
            if r.id == 15:
                assert cached['manual_confirmed'] and cached['selected']
            else:
                assert cached['selected'] is None and cached['selection_required']
                assert not cached['manual_confirmed']
        assert len(db.scalars(select(AuditLog).where(AuditLog.acao == 'CORRIGIR_LOCALIZACAO')).all()) == 4
        assert prepare(db, records()) == ([], [])
    response = client.get('/api/pickups', headers=admin_headers)
    mapped = {p['id']: p['location'] for p in response.json()}
    assert all(mapped[r.id] for r in records())
    assert mapped[81] is None


def test_unreviewed_candidates_do_not_appear_as_approved_locations():
    point = {'latitude': -23.4, 'longitude': -46.5}
    assert location_for_map({'schema_version': 2, 'candidates': [point]}) is None
    assert location_for_map({'candidates': [point]}) == point


def test_identity_or_address_change_aborts_before_mutation():
    with SessionLocal() as db:
        seed(db)
        db.get(Pickup, 77).endereco = 'Endereco atualizado por outro usuario'
        db.commit()
        with pytest.raises(ValueError, match='address changed'):
            prepare(db, records())
        assert db.get(Pickup, 34).endereco == records()[0].previous_address


def test_existing_manual_coordinate_cannot_be_overwritten():
    with SessionLocal() as db:
        seed(db)
        r = records()[1]
        db.add(GeocodedAddress(address=r.previous_address, result={
            'manual_confirmed': True, 'selected': {'latitude': -23.5, 'longitude': -46.6}}))
        db.commit()
        with pytest.raises(ValueError, match='Conflicting manual'):
            prepare(db, records())
