import pytest


def test_driver_can_report_available_vehicle_without_trip(client, driver_headers, admin_headers):
    response = client.post('/api/occurrences', headers=driver_headers, json={
        'vehicle_id': 1, 'tipo': 'LAVAGEM', 'descricao': 'Veiculo precisa de lavagem',
    })
    assert response.status_code == 201, response.text
    occurrence = response.json()
    assert occurrence['trip_id'] is None
    assert occurrence['vehicle_id'] == 1
    assert occurrence['driver_id'] == 1
    assert occurrence['vehicle_name'] == 'VW Delivery'
    assert occurrence['data_hora']
    listing = client.get('/api/occurrences?categoria=VEICULO&tipo=LAVAGEM', headers=admin_headers).json()
    assert listing['total'] == 1
    assert listing['items'][0]['id'] == occurrence['id']
    dashboard = client.get('/api/dashboard', headers=admin_headers).json()
    assert dashboard['total_occurrences'] == 1
    assert dashboard['total_trips'] == 0
    assert dashboard['vehicles'][0]['occurrences'] == 1
    assert dashboard['drivers'][0]['occurrences'] == 1
    assert client.patch(f"/api/occurrences/{occurrence['id']}", headers=admin_headers, json={'status': 'RESOLVIDA'}).status_code == 200


@pytest.mark.parametrize('vehicle_id', [None, 999])
def test_standalone_occurrence_requires_available_vehicle(client, driver_headers, vehicle_id):
    response = client.post('/api/occurrences', headers=driver_headers, json={
        'vehicle_id': vehicle_id, 'tipo': 'AVARIA', 'descricao': 'Avaria encontrada',
    })
    assert response.status_code == 400


def test_standalone_occurrence_rejects_unavailable_vehicle(client, driver_headers, admin_headers):
    assert client.put('/api/vehicles/1', headers=admin_headers, json={'status': 'ATENCAO'}).status_code == 200
    response = client.post('/api/occurrences', headers=driver_headers, json={
        'vehicle_id': 1, 'tipo': 'AVARIA', 'descricao': 'Avaria encontrada',
    })
    assert response.status_code == 400
