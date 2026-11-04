from conftest import assigned_plan, login


def create_purchasing(client, admin_headers):
    response = client.post('/api/users', headers=admin_headers, json={
        'nome': 'Equipe Compras', 'email': 'compras@example.com',
        'senha': 'Compras@123', 'role': 'COMPRAS',
    })
    assert response.status_code == 201, response.text
    return response.json(), login(client, 'compras@example.com', 'Compras@123')


def test_purchasing_permissions(client, admin_headers, driver_headers):
    account, headers = create_purchasing(client, admin_headers)
    assert account['role'] == 'COMPRAS'
    update = {'nome': account['nome'], 'email': account['email'], 'ativo': True}
    assert client.put(f"/api/users/{account['id']}", headers=admin_headers, json=update).json()['role'] == 'COMPRAS'
    assert any(u['id'] == account['id'] for u in client.get('/api/users', headers=admin_headers).json())
    for path in ['/api/tasks', '/api/tracking', '/api/tracking/1/history', '/api/trips']:
        response = client.get(path, headers=headers)
        assert response.status_code == 200, (path, response.text)
    task = client.post('/api/tasks', headers=headers, json={'titulo': 'Comprar material', 'endereco': 'Rua Teste', 'observacoes': 'Retirar pedido'})
    assert task.status_code == 201
    assert client.get(f"/api/tasks/{task.json()['id']}", headers=headers).status_code == 200
    for path in ['/api/users', '/api/dashboard', '/api/drivers', '/api/vehicles', '/api/vehicles/1', '/api/checklist-items', '/api/occurrences']:
        assert client.get(path, headers=headers).status_code == 403, path
    assert client.post('/api/users', headers=headers, json={'nome': 'Novo', 'email': 'novo@example.com', 'senha': 'Senha@123'}).status_code == 403
    assert client.put('/api/tracking/1/link', headers=headers, json={'tracker_id': '123'}).status_code == 403
    assert client.get('/api/tasks/mine', headers=headers).status_code == 403
    assert client.post(f"/api/tasks/{task.json()['id']}/accept", headers=headers).status_code == 403
    plan_id = assigned_plan()
    trip = client.post('/api/trips', headers=driver_headers, json={'vehicle_id': 1, 'km_inicial': 1000, 'route_plan_id': plan_id})
    assert trip.status_code == 201, trip.text
    data = trip.json()
    assert client.get(f"/api/trips/{data['id']}", headers=headers).status_code == 200
    assert client.get(f"/api/occurrences?trip_id={data['id']}", headers=headers).status_code == 200
    assert client.get(f"/api/trips/{data['id']}/deliveries", headers=headers).status_code == 200


def test_role_changes_apply_to_existing_sessions(client, admin_headers):
    account, headers = create_purchasing(client, admin_headers)
    body = {'nome': account['nome'], 'email': account['email'], 'ativo': True, 'role': 'ADMIN'}
    assert client.put(f"/api/users/{account['id']}", headers=admin_headers, json=body).status_code == 200
    assert client.get('/api/dashboard', headers=headers).status_code == 200
    body['role'] = 'COMPRAS'
    assert client.put(f"/api/users/{account['id']}", headers=admin_headers, json=body).status_code == 200
    assert client.get('/api/dashboard', headers=headers).status_code == 403
    body.update(nome='Admin', email='admin@example.com')
    assert client.put('/api/users/1', headers=admin_headers, json=body).status_code == 400
    assert client.patch(f"/api/users/{account['id']}/status", headers=admin_headers, json={'ativo': False}).status_code == 200
    assert client.get('/api/tasks', headers=headers).status_code == 401
