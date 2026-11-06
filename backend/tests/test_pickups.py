def test_pickup_create_list_update(client, admin_headers):
    data = {"nome": " Costureira Maria ", "telefone": "11999999999", "endereco": "Rua das Flores, 10"}
    response = client.post("/api/pickups", headers=admin_headers, json=data)
    assert response.status_code == 201
    item = response.json()
    assert item["nome"] == "Costureira Maria"
    assert client.get("/api/pickups", headers=admin_headers).json() == [item]
    data["endereco"] = "Rua Nova, 20"
    response = client.put(f"/api/pickups/{item['id']}", headers=admin_headers, json=data)
    assert response.status_code == 200
    assert response.json()["endereco"] == "Rua Nova, 20"
    assert client.get("/api/pickups", headers=admin_headers).json()[0]["endereco"] == "Rua Nova, 20"


def test_pickup_validation_and_access(client, admin_headers, driver_headers):
    data = {"nome": "Maria", "telefone": "123", "endereco": "Rua A"}
    assert client.get("/api/pickups").status_code == 401
    assert client.get("/api/pickups", headers=driver_headers).status_code == 403
    assert client.post("/api/pickups", headers=driver_headers, json=data).status_code == 403
    assert client.put("/api/pickups/1", headers=driver_headers, json=data).status_code == 403
    for field in data:
        assert client.post("/api/pickups", headers=admin_headers, json={**data, field: "  "}).status_code == 422
    assert client.put("/api/pickups/999", headers=admin_headers, json=data).status_code == 404


def test_pickup_status_and_delete(client, admin_headers, driver_headers):
    data = {"nome": "Fornecedor", "telefone": "123", "endereco": "Rua A"}
    item = client.post("/api/pickups", headers=admin_headers, json=data).json()
    url = f"/api/pickups/{item['id']}"
    assert item["ativo"] is True
    assert client.patch(url + "/status", headers=driver_headers, json={"ativo": False}).status_code == 403
    assert client.delete(url, headers=driver_headers).status_code == 403
    for active in (False, True, False):
        response = client.patch(url + "/status", headers=admin_headers, json={"ativo": active})
        assert response.status_code == 200
        assert response.json()["ativo"] is active
        assert client.get("/api/pickups", headers=admin_headers).json()[0]["ativo"] is active
    assert client.put(url, headers=admin_headers, json=data).json()["ativo"] is False
    assert client.delete(url, headers=admin_headers).status_code == 204
    assert client.get("/api/pickups", headers=admin_headers).json() == []
    assert client.delete(url, headers=admin_headers).status_code == 404
    assert client.patch(url + "/status", headers=admin_headers, json={"ativo": True}).status_code == 404


def test_pickup_types(client, admin_headers):
    data = {"nome": "Contato", "telefone": "123", "endereco": "Rua A", "tipo": "COSTUREIRA"}
    response = client.post("/api/pickups", headers=admin_headers, json=data)
    assert response.status_code == 201
    assert response.json()["tipo"] == "COSTUREIRA"
    url = f"/api/pickups/{response.json()['id']}"
    data["tipo"] = "FLORISTA"
    assert client.put(url, headers=admin_headers, json=data).json()["tipo"] == "FLORISTA"
    assert client.get("/api/pickups", headers=admin_headers).json()[0]["tipo"] == "FLORISTA"
    data["tipo"] = "FORNECEDOR"
    response = client.put(url, headers=admin_headers, json=data)
    assert response.status_code == 200
    assert response.json()["tipo"] == "FORNECEDOR"
    assert client.get("/api/pickups", headers=admin_headers).json()[0]["tipo"] == "FORNECEDOR"
    response = client.post("/api/pickups", headers=admin_headers, json=data)
    assert response.status_code == 201
    assert response.json()["tipo"] == "FORNECEDOR"
    data.pop("tipo")
    assert client.put(url, headers=admin_headers, json=data).json()["tipo"] == "FORNECEDOR"
    for invalid in ("OUTRO", "", "costureira"):
        assert client.post("/api/pickups", headers=admin_headers, json={**data, "tipo": invalid}).status_code == 422
    assert client.post("/api/pickups", headers=admin_headers, json=data).json()["tipo"] is None


def test_pickup_established_route_link(client, admin_headers):
    route = client.post('/api/route-templates', headers=admin_headers, json={'name': 'Rota de coletas'}).json()
    data = {'nome': 'Fornecedor A', 'telefone': '123', 'endereco': 'Rua A', 'tipo': 'FORNECEDOR', 'route_template_id': route['id']}
    response = client.post('/api/pickups', headers=admin_headers, json=data)
    assert response.status_code == 201, response.text
    assert response.json()['route_template_id'] == route['id']
    url = f"/api/pickups/{response.json()['id']}"
    assert client.get('/api/pickups', headers=admin_headers).json()[0]['route_template_id'] == route['id']
    without_link = {key: value for key, value in data.items() if key != 'route_template_id'}
    assert client.put(url, headers=admin_headers, json=without_link).json()['route_template_id'] == route['id']
    assert client.put(url, headers=admin_headers, json={**data, 'route_template_id': None}).json()['route_template_id'] is None
    for invalid in (0, -1, 99999):
        invalid_data = {**data, 'route_template_id': invalid}
        assert client.post('/api/pickups', headers=admin_headers, json=invalid_data).status_code == 422
        assert client.put(url, headers=admin_headers, json=invalid_data).status_code == 422
    assert client.put(url, headers=admin_headers, json=data).status_code == 200
    assert client.delete(f"/api/route-templates/{route['id']}?revision=0", headers=admin_headers).status_code == 204
    assert client.get('/api/pickups', headers=admin_headers).json()[0]['route_template_id'] is None
