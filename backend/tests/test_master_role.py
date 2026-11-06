from conftest import login


def test_master_full_panel_access_and_user_management(client, admin_headers):
    payload = {'nome': 'Master', 'email': 'master@example.com', 'senha': 'Master@123', 'role': 'MASTER'}
    response = client.post('/api/users', headers=admin_headers, json=payload)
    assert response.status_code == 201, response.text
    account = response.json()
    assert account['role'] == 'MASTER'
    headers = login(client, payload['email'], payload['senha'])
    for path in ['/api/dashboard', '/api/users', '/api/drivers', '/api/vehicles', '/api/vehicles/1', '/api/checklist-items', '/api/occurrences', '/api/tasks', '/api/tracking', '/api/tracking/1/history', '/api/trips', '/api/route-plans']:
        result = client.get(path, headers=headers)
        assert result.status_code == 200, (path, result.text)
    result = client.post('/api/users', headers=headers, json={'nome': 'Outro Master', 'email': 'outro@example.com', 'senha': 'Master@456', 'role': 'MASTER'})
    assert result.status_code == 201, result.text
    other = result.json()
    update = {'nome': 'Master atualizado', 'email': other['email'], 'role': 'COMPRAS', 'ativo': True}
    assert client.put(f"/api/users/{other['id']}", headers=headers, json=update).json()['role'] == 'COMPRAS'
    assert client.patch(f"/api/users/{other['id']}/status", headers=headers, json={'ativo': False}).status_code == 200
    assert client.post('/api/checklist-items', headers=headers, json={'nome': 'Verificação master', 'ordem': 4, 'obrigatorio': True}).status_code == 201
    assert client.put('/api/tracking/1/link', headers=headers, json={'tracker_id': '123'}).status_code == 200
    assert client.post('/api/tasks', headers=headers, json={'titulo': 'Tarefa master', 'endereco': 'Rua Teste', 'observacoes': 'Retirar material'}).status_code == 201
    assert client.patch(f"/api/users/{account['id']}/status", headers=admin_headers, json={'ativo': False}).status_code == 200
    assert client.get('/api/users', headers=headers).status_code == 401
