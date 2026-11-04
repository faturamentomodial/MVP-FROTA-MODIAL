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
