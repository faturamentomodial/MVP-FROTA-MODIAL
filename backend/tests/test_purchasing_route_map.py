from conftest import login
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models import User
from app.models.enums import UserRole
from app.services import route_planning as provider
from test_route_plans import payload
from test_route_templates import template_body


def test_purchasing_can_read_map_without_management_access(client, admin_headers, driver_headers, monkeypatch):
    with SessionLocal() as db:
        db.add(User(nome='Compras', email='compras@example.com',
                    senha_hash=get_password_hash('Compras@123'), role=UserRole.COMPRAS))
        db.commit()
    headers = login(client, 'compras@example.com', 'Compras@123')
    plan = client.post('/api/route-plans', headers=admin_headers, json=payload())
    route = client.post('/api/route-templates', headers=admin_headers, json=template_body())
    assert plan.status_code == route.status_code == 201
    plan_id, route_id = plan.json()['id'], route.json()['id']
    monkeypatch.setattr(provider, 'geocode', lambda address: {'candidates': []})
    for url in ['/route-plans', f'/route-plans/{plan_id}', '/route-templates',
                f'/route-templates/{route_id}', '/pickups', '/route-plans/geocode?address=Rua%20Teste']:
        assert client.get('/api' + url, headers=headers).status_code == 200, url
        assert client.get('/api' + url, headers=driver_headers).status_code == 403, url
        assert client.get('/api' + url).status_code == 401, url
    for method, url, body in [
        ('POST', '/route-plans', payload()),
        ('PUT', f'/route-plans/{plan_id}', payload()),
        ('DELETE', f'/route-plans/{plan_id}?revision=0', None),
        ('POST', f'/route-plans/{plan_id}/calculate', {'revision': 0}),
        ('POST', f'/route-plans/{plan_id}/confirm', {'revision': 0}),
        ('POST', '/route-templates', template_body()),
        ('PUT', f'/route-templates/{route_id}', template_body()),
        ('DELETE', f'/route-templates/{route_id}?revision=0', None),
        ('POST', f'/route-templates/{route_id}/calculate', {'revision': 0}),
        ('POST', f'/route-templates/{route_id}/duplicate', None),
        ('POST', '/pickups', {'nome': 'Coleta', 'telefone': '11999999999', 'endereco': 'Rua Teste'}),
    ]:
        assert client.request(method, '/api' + url, headers=headers, json=body).status_code == 403, url
    assert client.get('/api/route-executions', headers=headers).status_code == 403
