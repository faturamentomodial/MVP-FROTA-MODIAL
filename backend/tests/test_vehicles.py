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



def test_rotation_schedule_and_plate_update(client, admin_headers):
    # All ten endings, including both old and Mercosur formats.
    expected = ["Sexta-feira", "Segunda-feira", "Segunda-feira", "Ter\u00e7a-feira", "Ter\u00e7a-feira",
                "Quarta-feira", "Quarta-feira", "Quinta-feira", "Quinta-feira", "Sexta-feira"]
    for digit, day in enumerate(expected):
        plate = f"ROT1A2{digit}" if digit % 2 else f"ROT-123{digit}"
        response = client.post("/api/vehicles", headers=admin_headers, json={
            "placa": plate, "marca": "VW", "modelo": "Teste", "tipo": "Carro", "km_atual": 0,
        })
        assert response.status_code == 201, response.text
        assert response.json()["rodizio_dia"] == day
    # Existing records receive the computed schedule without a migration.
    existing = client.get("/api/vehicles/1", headers=admin_headers)
    assert existing.json()["rodizio_dia"] == "Ter\u00e7a-feira"
    updated = client.put("/api/vehicles/1", headers=admin_headers, json={"placa": "ABC-1230"})
    assert updated.json()["rodizio_dia"] == "Sexta-feira"
    listed = client.get("/api/vehicles?available=true", headers=admin_headers).json()["items"]
    assert next(v for v in listed if v["id"] == 1)["rodizio_dia"] == "Sexta-feira"


def test_unknown_plate_has_no_rotation_day():
    from app.services.vehicle_restrictions import restriction_day
    assert restriction_day("INVALID") is None
    assert restriction_day("abc-1234") == "Ter\u00e7a-feira"
