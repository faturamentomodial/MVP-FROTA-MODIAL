from conftest import assigned_plan


def test_deleting_used_item_preserves_history(client, admin_headers, driver_headers):
    trip = client.post('/api/trips', headers=driver_headers, json={
        'route_plan_id': assigned_plan(), 'vehicle_id': 1, 'km_inicial': 1000,
    }).json()
    items = client.get('/api/checklist-items', headers=driver_headers).json()
    checklist = client.post(f"/api/trips/{trip['id']}/checklist", headers=driver_headers, json={
        'answers': [{'checklist_item_id': item['id'], 'status': 'OK'} for item in items],
    })
    assert checklist.status_code == 201
    item_id = items[0]['id']
    assert client.delete(f'/api/checklist-items/{item_id}', headers=driver_headers).status_code == 403
    assert client.delete(f'/api/checklist-items/{item_id}', headers=admin_headers).status_code == 204
    for query in ['', '?active_only=false']:
        remaining = client.get(f'/api/checklist-items{query}', headers=admin_headers).json()
        assert item_id not in {item['id'] for item in remaining}
    history = client.get(f"/api/checklists/{checklist.json()['id']}", headers=admin_headers).json()
    assert history['answers'][0]['item']['nome'] == items[0]['nome']
    assert client.put(f'/api/checklist-items/{item_id}', headers=admin_headers, json={'ativo': True}).status_code == 404
    assert client.delete(f'/api/checklist-items/{item_id}', headers=admin_headers).status_code == 404


def test_can_delete_inactive_item(client, admin_headers):
    item = client.post('/api/checklist-items', headers=admin_headers, json={'nome': 'Item inativo', 'ativo': False}).json()
    assert client.delete(f"/api/checklist-items/{item['id']}", headers=admin_headers).status_code == 204
    assert client.delete('/api/checklist-items/99999', headers=admin_headers).status_code == 404
