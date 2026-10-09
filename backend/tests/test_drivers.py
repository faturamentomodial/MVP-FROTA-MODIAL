def test_register_multiple_drivers_with_only_required_fields(client, admin_headers):
    for index in range(2):
        payload = {"nome": f"Motorista {index}", "email": f"novo{index}@example.com", "senha": "Driver@123"}
        response = client.post("/api/drivers", headers=admin_headers, json=payload)
        assert response.status_code == 201, response.text
        driver = response.json()
        assert driver["ativo"] is True
        assert driver["cpf"] == ""
        assert driver["telefone"] == ""
        assert client.post("/api/auth/login", json={"email": payload["email"], "senha": payload["senha"]}).status_code == 200
        assert client.put(f"/api/drivers/{driver['id']}", headers=admin_headers, json={"nome": "Nome atualizado", "email": payload["email"]}).status_code == 200
