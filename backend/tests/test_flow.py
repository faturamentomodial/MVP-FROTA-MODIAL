from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models import Driver, User, Vehicle
from app.models.enums import UserRole


def test_complete_driver_flow_and_dashboard(client, admin_headers, driver_headers):
    vehicles = client.get("/api/vehicles?available=true", headers=driver_headers).json()["items"]
    trip = client.post("/api/trips", headers=driver_headers, json={"vehicle_id": vehicles[0]["id"], "km_inicial": 1000})
    assert trip.status_code == 201
    trip_id = trip.json()["id"]

    second = client.post("/api/trips", headers=driver_headers, json={"vehicle_id": vehicles[0]["id"], "km_inicial": 1000})
    assert second.status_code == 409

    start_early = client.post(f"/api/trips/{trip_id}/start", headers=driver_headers)
    assert start_early.status_code == 400

    duplicate_cargo = client.put(f"/api/trips/{trip_id}/cargo", headers=driver_headers, json={
        "notas": [{"numero_nota": "NF-100", "volumes": 3}, {"numero_nota": "nf-100", "volumes": 2}]
    })
    assert duplicate_cargo.status_code == 422

    cargo = client.put(f"/api/trips/{trip_id}/cargo", headers=driver_headers, json={
        "notas": [{"numero_nota": "NF-100", "volumes": 3}, {"numero_nota": "NF-101", "volumes": 2}]
    })
    assert cargo.status_code == 200
    assert cargo.json()["total_volumes"] == 5
    assert len(cargo.json()["notas"]) == 2

    items = client.get("/api/checklist-items", headers=driver_headers).json()
    incomplete = client.post(f"/api/trips/{trip_id}/checklist", headers=driver_headers, json={
        "answers": [{"checklist_item_id": items[0]["id"], "status": "OK"}]
    })
    assert incomplete.status_code == 400

    answers = [{"checklist_item_id": item["id"], "status": "OK"} for item in items]
    answers[0] = {"checklist_item_id": items[0]["id"], "status": "PROBLEMA", "observacao": "Sulco próximo ao limite"}
    checklist = client.post(f"/api/trips/{trip_id}/checklist", headers=driver_headers, json={"answers": answers})
    assert checklist.status_code == 201
    assert checklist.json()["status"] == "COM_PROBLEMAS"
    assert len(checklist.json()["answers"]) == len(items)

    started = client.post(f"/api/trips/{trip_id}/start", headers=driver_headers)
    assert started.status_code == 200
    assert started.json()["status"] == "EM_ANDAMENTO"

    occurrence = client.post("/api/occurrences", headers=driver_headers, json={
        "trip_id": trip_id, "tipo": "PNEU", "descricao": "Pneu perdeu pressão", "local": "Guarulhos"
    })
    assert occurrence.status_code == 201
    assert "attachments" not in occurrence.json()
    assert occurrence.json()["driver_id"] == trip.json()["driver_id"]
    assert occurrence.json()["vehicle_id"] == trip.json()["vehicle_id"]
    occurrence_id = occurrence.json()["id"]
    fetched = client.get(f"/api/occurrences/{occurrence_id}", headers=admin_headers)
    assert fetched.status_code == 200
    assert fetched.json()["descricao"] == "Pneu perdeu pressão"
    assert fetched.json()["local"] == "Guarulhos"
    assert "attachments" not in fetched.json()
    updated = client.patch(f"/api/occurrences/{occurrence_id}", headers=admin_headers, json={"status": "EM_ANALISE", "observacao_gestor": "Em tratativa"})
    assert updated.json()["status"] == "EM_ANALISE"

    invalid_finish = client.post(f"/api/trips/{trip_id}/finish", headers=driver_headers, json={"km_final": 999})
    assert invalid_finish.status_code == 400
    for invoice in cargo.json()["notas"]:
        url = f"/api/trips/{trip_id}/deliveries/{invoice['id']}"
        assert client.post(url + "/start", headers=driver_headers).status_code == 200
        assert client.post(url + "/finish", headers=driver_headers).status_code == 200
    finished = client.post(f"/api/trips/{trip_id}/finish", headers=driver_headers, json={"km_final": 1267})
    assert finished.status_code == 200
    assert finished.json()["km_percorrido"] == 267
    vehicle = client.get(f"/api/vehicles/{trip.json()['vehicle_id']}", headers=admin_headers).json()
    assert vehicle["km_atual"] == 1267
    assert vehicle["status"] == "DISPONIVEL"

    dashboard = client.get("/api/dashboard", headers=admin_headers)
    assert dashboard.status_code == 200, dashboard.text
    data = dashboard.json()
    assert data["total_trips"] == 1
    assert data["total_checklists"] == 1
    assert data["total_occurrences"] == 1
    assert data["total_km"] == 267


def test_vehicle_cannot_be_in_two_open_trips(client, driver_headers):
    with SessionLocal() as db:
        second_user = User(nome="Maria", email="maria@example.com", senha_hash=get_password_hash("Driver@123"), role=UserRole.MOTORISTA)
        db.add(Driver(nome="Maria", cpf="12345678902", telefone="11988888888", user=second_user))
        db.commit()
    vehicle = client.get("/api/vehicles?available=true", headers=driver_headers).json()["items"][0]
    assert client.post("/api/trips", headers=driver_headers, json={"vehicle_id": vehicle["id"], "km_inicial": 1000}).status_code == 201
    login = client.post("/api/auth/login", json={"email": "maria@example.com", "senha": "Driver@123"}).json()
    maria = {"Authorization": f"Bearer {login['access_token']}"}
    blocked = client.post("/api/trips", headers=maria, json={"vehicle_id": vehicle["id"], "km_inicial": 1000})
    assert blocked.status_code == 409
