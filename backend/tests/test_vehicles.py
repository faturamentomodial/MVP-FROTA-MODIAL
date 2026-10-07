def test_vehicle_crud_and_logical_deactivation(client, admin_headers):
    created = client.post("/api/vehicles", headers=admin_headers, json={
        "placa": "XYZ9A99", "marca": "Iveco", "modelo": "Daily", "tipo": "Furgão",
        "km_atual": 500, "status": "DISPONIVEL", "ativo": True,
    })
    assert created.status_code == 201
    vehicle_id = created.json()["id"]
    edited = client.put(f"/api/vehicles/{vehicle_id}", headers=admin_headers, json={"modelo": "Daily 35-160"})
    assert edited.status_code == 200
    assert edited.json()["modelo"] == "Daily 35-160"
    disabled = client.patch(f"/api/vehicles/{vehicle_id}/status", headers=admin_headers, json={"ativo": False})
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "INATIVO"

