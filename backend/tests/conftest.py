import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///./test_fleet.db"
os.environ["SECRET_KEY"] = "test-secret-key-with-more-than-thirty-two-characters"
os.environ["ENVIRONMENT"] = "test"

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.core.security import get_password_hash
from app.main import app
from app.models import ChecklistItem, Driver, User, Vehicle
from app.models.enums import UserRole


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        admin = User(nome="Admin", email="admin@example.com", senha_hash=get_password_hash("Admin@123"), role=UserRole.ADMIN)
        user = User(nome="João Silva", email="driver@example.com", senha_hash=get_password_hash("Driver@123"), role=UserRole.MOTORISTA)
        driver = Driver(nome="João Silva", cpf="12345678901", telefone="11999999999", user=user)
        vehicle = Vehicle(placa="ABC1D23", marca="VW", modelo="Delivery", tipo="Baú", km_atual=1000)
        items = [ChecklistItem(nome=name, ordem=index, obrigatorio=True) for index, name in enumerate(("Pneus", "Freios", "Faróis"), start=1)]
        db.add_all([admin, driver, vehicle, *items])
        db.commit()
    yield


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=True) as test_client:
        yield test_client


def login(client: TestClient, email="admin@example.com", senha="Admin@123") -> dict:
    response = client.post("/api/auth/login", json={"email": email, "senha": senha})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def admin_headers(client):
    return login(client)


@pytest.fixture
def driver_headers(client):
    return login(client, "driver@example.com", "Driver@123")


def assigned_plan(vehicle_id=1, driver_id=1, notes=None):
    """Seed a confirmed manager assignment for operational tests."""
    from app.models.route_plans import RoutePlan
    point = {'address': 'Rua Teste', 'latitude': -23.5, 'longitude': -46.6}
    with SessionLocal() as db:
        plan = RoutePlan(status='CONFIRMADO', created_by=1, data={
            'name': 'Rota de teste', 'vehicle_id': vehicle_id, 'driver_id': driver_id,
            'origin': point, 'profile': 'truck', 'invoices': [
                {'number': n['numero_nota'], 'volumes': n['volumes'], 'destination': point}
                for n in (notes or [{'numero_nota': 'NF-100', 'volumes': 3}, {'numero_nota': 'NF-101', 'volumes': 2}])
            ]
        })
        db.add(plan)
        db.commit()
        return plan.id
