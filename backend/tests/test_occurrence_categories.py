from conftest import assigned_plan


def test_driver_occurrences_are_filtered_by_category(client, admin_headers, driver_headers):
    trip = client.post('/api/trips', headers=driver_headers, json={
        'route_plan_id': assigned_plan(), 'vehicle_id': 1, 'km_inicial': 1000,
    })
    assert trip.status_code == 201
    trip_id = trip.json()['id']
    items = client.get('/api/checklist-items', headers=driver_headers).json()
    checklist = client.post(f'/api/trips/{trip_id}/checklist', headers=driver_headers, json={
        'answers': [{'checklist_item_id': item['id'], 'status': 'OK'} for item in items],
    })
    assert checklist.status_code == 201
    assert client.post(f'/api/trips/{trip_id}/start', headers=driver_headers).status_code == 200

    categories = {
        'VEICULO': {'AVARIA', 'PROBLEMA_MECANICO', 'PROBLEMA_ELETRICO', 'PNEU', 'MULTA', 'ABASTECIMENTO', 'LAVAGEM'},
        'ROTA': {'ACIDENTE', 'PROBLEMA_ENTREGA', 'CLIENTE_AUSENTE', 'ATRASO'},
        'OUTROS': {'OUTRO'},
    }
    for types in categories.values():
        for occurrence_type in types:
            response = client.post('/api/occurrences', headers=driver_headers, json={
                'trip_id': trip_id, 'tipo': occurrence_type, 'descricao': f'Registro de {occurrence_type}',
            })
            assert response.status_code == 201, response.text

    for category, types in categories.items():
        response = client.get(f'/api/occurrences?categoria={category}', headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data['total'] == len(types)
        assert {item['tipo'] for item in data['items']} == types
        assert all(item['vehicle_name'] == 'VW Delivery' and item['data_hora'] for item in data['items'])
        for occurrence_type in types:
            result = client.get(f'/api/occurrences?categoria={category}&tipo={occurrence_type}', headers=admin_headers).json()
            assert result['total'] == 1
            assert result['items'][0]['tipo'] == occurrence_type
        incompatible = client.get(f'/api/occurrences?categoria={category}&tipo=INVALIDO', headers=admin_headers)
        assert incompatible.status_code == 422


    filtered = client.get('/api/occurrences?categoria=OUTROS&status=RESOLVIDA', headers=admin_headers).json()
    assert filtered['total'] == 0
    assert client.get('/api/occurrences', headers=admin_headers).json()['total'] == 12
