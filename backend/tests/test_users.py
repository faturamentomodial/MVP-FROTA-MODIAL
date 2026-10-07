from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import verify_password
from app.models import AuditLog, User


def manager_payload(**changes):
    return {"nome": "Maria Gestora", "email": "maria@example.com", "senha": "Gestora@123", "ativo": True, **changes}


def test_create_manager_login_and_safe_audit(client, admin_headers):
    response = client.post("/api/users", headers=admin_headers, json=manager_payload())
    assert response.status_code == 201
    account = response.json()
    assert account["role"] == "ADMIN"
    assert "senha_hash" not in account and "senha" not in account
    response = client.post("/api/auth/login", json={"email": "maria@example.com", "senha": "Gestora@123"})
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    assert client.get("/api/dashboard", headers=headers).status_code == 200
    with SessionLocal() as db:
        assert verify_password("Gestora@123", db.get(User, account["id"]).senha_hash)
        log = db.scalar(select(AuditLog).where(AuditLog.entidade == "USER"))
        assert log.entidade_id == account["id"]
        assert "Gestora@123" not in str(log.detalhes)


def test_managers_only_and_authorization(client, admin_headers, driver_headers):
    users = client.get("/api/users", headers=admin_headers).json()
    assert len(users) == 1 and all(user["role"] == "ADMIN" for user in users)
    for method, path, body in [("get", "/api/users", None), ("post", "/api/users", manager_payload()), ("put", "/api/users/1", manager_payload()), ("patch", "/api/users/1/status", {"ativo": False})]:
        assert client.request(method, path, headers=driver_headers, json=body).status_code == 403
        assert client.request(method, path, json=body).status_code == 401
    assert client.put("/api/users/2", headers=admin_headers, json=manager_payload()).status_code == 404


def test_duplicates_validation_and_fixed_role(client, admin_headers):
    for changes, status in [({"email": "ADMIN@example.com"}, 409), ({"email": "driver@example.com"}, 409), ({"senha": "curta"}, 422), ({"nome": "  "}, 422), ({"role": "MOTORISTA"}, 422)]:
        assert client.post("/api/users", headers=admin_headers, json=manager_payload(**changes)).status_code == status


def test_edit_password_and_account_status(client, admin_headers):
    account = client.post("/api/users", headers=admin_headers, json=manager_payload()).json()
    login = client.post("/api/auth/login", json={"email": "maria@example.com", "senha": "Gestora@123"}).json()
    session = {"Authorization": f"Bearer {login['access_token']}"}
    update = {"nome": "Maria Atualizada", "email": "nova@example.com", "ativo": True}
    assert client.put(f"/api/users/{account['id']}", headers=admin_headers, json=update).status_code == 200
    assert client.post("/api/auth/login", json={"email": "nova@example.com", "senha": "Gestora@123"}).status_code == 200
    update["senha"] = "NovaSenha@456"
    assert client.put(f"/api/users/{account['id']}", headers=admin_headers, json=update).status_code == 200
    assert client.post("/api/auth/login", json={"email": "nova@example.com", "senha": "Gestora@123"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "nova@example.com", "senha": "NovaSenha@456"}).status_code == 200
    assert client.patch(f"/api/users/{account['id']}/status", headers=admin_headers, json={"ativo": False}).status_code == 200
    assert client.get("/api/dashboard", headers=session).status_code == 401
    assert client.post("/api/auth/login", json={"email": "nova@example.com", "senha": "NovaSenha@456"}).status_code == 403
    assert client.patch(f"/api/users/{account['id']}/status", headers=admin_headers, json={"ativo": True}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "nova@example.com", "senha": "NovaSenha@456"}).status_code == 200


def test_cannot_disable_own_account(client, admin_headers):
    assert client.patch("/api/users/1/status", headers=admin_headers, json={"ativo": False}).status_code == 400
    payload = {"nome": "Admin", "email": "admin@example.com", "ativo": False}
    assert client.put("/api/users/1", headers=admin_headers, json=payload).status_code == 400
    payload["ativo"] = True
    assert client.put("/api/users/1", headers=admin_headers, json=payload).status_code == 200


def test_password_spaces_are_preserved(client, admin_headers):
    password = "  Gestora@123  "
    assert client.post("/api/users", headers=admin_headers, json=manager_payload(senha=password)).status_code == 201
    assert client.post("/api/auth/login", json={"email": "maria@example.com", "senha": password}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "maria@example.com", "senha": password.strip()}).status_code == 401
