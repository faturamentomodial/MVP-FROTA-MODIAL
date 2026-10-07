from app.core.database import SessionLocal
from app.models import User


def test_valid_and_invalid_login(client):
    valid = client.post("/api/auth/login", json={"email": "admin@example.com", "senha": "Admin@123"})
    assert valid.status_code == 200
    assert valid.json()["user"]["role"] == "ADMIN"
    invalid = client.post("/api/auth/login", json={"email": "admin@example.com", "senha": "wrong-password"})
    assert invalid.status_code == 401


def test_inactive_user_cannot_login(client):
    with SessionLocal() as db:
        user = db.query(User).filter_by(email="driver@example.com").one()
        user.ativo = False
        db.commit()
    response = client.post("/api/auth/login", json={"email": "driver@example.com", "senha": "Driver@123"})
    assert response.status_code == 403
