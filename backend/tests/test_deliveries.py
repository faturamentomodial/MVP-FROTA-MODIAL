from datetime import UTC, datetime
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models import AuditLog, Driver, Occurrence, User
from app.models.enums import UserRole


def prepare(client, headers, count=1):
    vehicle = client.get("/api/vehicles?available=true", headers=headers).json()["items"][0]
    trip = client.post("/api/trips", headers=headers, json={"vehicle_id": vehicle["id"], "km_inicial": 1000}).json()
    tid = trip["id"]
    cargo = client.put(f"/api/trips/{tid}/cargo", headers=headers, json={"notas": [
        {"numero_nota": str(1001+i), "volumes": i+1} for i in range(count)
    ]})
    assert cargo.status_code == 200
    items = client.get("/api/checklist-items", headers=headers).json()
    assert client.post(f"/api/trips/{tid}/checklist", headers=headers, json={
        "answers": [{"checklist_item_id": i["id"], "status": "OK"} for i in items]
    }).status_code == 201
    assert client.post(f"/api/trips/{tid}/start", headers=headers).status_code == 200
    return tid, cargo.json()["notas"]


def stamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert result.utcoffset().total_seconds() == 0
    return result


def test_one_invoice_server_timestamps_history_and_duplicates(client, driver_headers, admin_headers):
    tid, notes = prepare(client, driver_headers)
    url = f"/api/trips/{tid}/deliveries/{notes[0]['id']}"
    assert client.post(url+"/finish", headers=driver_headers).status_code == 409
    before = datetime.now(UTC)
    started = client.post(url+"/start", headers=driver_headers, json={"started_at": "2000-01-01T00:00:00Z"})
    assert started.status_code == 200, started.text
    assert before <= stamp(started.json()["started_at"]) <= datetime.now(UTC)
    assert client.post(url+"/start", headers=driver_headers).status_code == 409
    delivered = client.post(url+"/finish", headers=driver_headers, json={"delivered_at": "2000-01-01T00:00:00Z"})
    assert delivered.status_code == 200, delivered.text
    data = delivered.json()
    assert data["status"] == "ENTREGUE"
    assert stamp(data["delivered_at"]) >= stamp(data["started_at"])
    assert data["started_at"] == started.json()["started_at"]
    assert client.post(url+"/finish", headers=driver_headers).status_code == 409
    assert client.post(url+"/occurrence", headers=driver_headers, json={"motivo": "CLIENTE_FECHADO"}).status_code == 409
    assert client.get(url, headers=driver_headers).json() == data
    with SessionLocal() as db:
        logs = list(db.scalars(select(AuditLog).where(AuditLog.entidade == "TRIP_INVOICE")))
        assert len(logs) == 2
        assert logs[1].detalhes["status_anterior"] == "EM_ENTREGA"
        assert logs[1].detalhes["status_novo"] == "ENTREGUE"
        assert logs[1].detalhes["trip_id"] == tid
        assert logs[1].user_id is not None
    summary = client.get("/api/dashboard", headers=admin_headers).json()["delivery_routes"][0]
    assert summary["total"] == summary["delivered"] == 1
    assert summary["pending"] == summary["failed"] == 0
    assert summary["last_delivered_at"] == data["delivered_at"]
    assert client.post(f"/api/trips/{tid}/finish", headers=driver_headers, json={"km_final": 1100}).status_code == 200
    assert client.post(url+"/start", headers=driver_headers).status_code == 409


def test_five_invoice_sequence_occurrence_and_dashboard(client, driver_headers, admin_headers):
    tid, notes = prepare(client, driver_headers, 5)
    root = f"/api/trips/{tid}/deliveries"
    assert len(client.get(root, headers=driver_headers).json()) == 5
    assert client.get(f"{root}/{notes[4]['id']}", headers=driver_headers).status_code == 200
    assert client.post(f"{root}/{notes[1]['id']}/start", headers=driver_headers).status_code == 409
    for i,n in enumerate(notes[:4]):
        url = f"{root}/{n['id']}"
        assert client.post(url+"/start", headers=driver_headers).status_code == 200
        if i == 2:
            before = datetime.now(UTC)
            payload = {"motivo": "CLIENTE_FECHADO", "observacao": "Loja fechada"}
            occurrence = client.post(url+"/occurrence", headers=driver_headers, json=payload)
            assert occurrence.status_code == 200, occurrence.text
            assert before <= stamp(occurrence.json()["occurrence_at"]) <= datetime.now(UTC)
            assert client.post(url+"/occurrence", headers=driver_headers, json=payload).status_code == 409
            assert client.post(url+"/finish", headers=driver_headers).status_code == 409
        else:
            assert client.post(url+"/finish", headers=driver_headers).status_code == 200
    result = client.get(root, headers=driver_headers).json()
    assert [n["status"] for n in result] == ["ENTREGUE", "ENTREGUE", "NAO_ENTREGUE", "ENTREGUE", "PENDENTE"]
    timestamps = [n["delivered_at"] or n["occurrence_at"] for n in result[:4]]
    assert len(set(timestamps)) == 4
    assert result[4]["started_at"] is None
    assert client.post(f"/api/trips/{tid}/finish", headers=driver_headers, json={"km_final": 1100}).status_code == 409
    summary = client.get("/api/dashboard", headers=admin_headers).json()["delivery_routes"][0]
    assert (summary["total"],summary["delivered"],summary["failed"],summary["pending"]) == (5,3,1,1)
    occurrences = client.get(f"/api/occurrences?trip_id={tid}", headers=admin_headers).json()["items"]
    assert len(occurrences) == 1
    assert occurrences[0]["invoice_id"] == notes[2]["id"]
    assert occurrences[0]["data_hora"] == result[2]["occurrence_at"]


def test_access_missing_routes_and_other_driver(client, driver_headers, admin_headers):
    tid, notes = prepare(client, driver_headers)
    url = f"/api/trips/{tid}/deliveries/{notes[0]['id']}"
    with SessionLocal() as db:
        user = User(nome="Outro",email="other@example.com",senha_hash=get_password_hash("Driver@123"),role=UserRole.MOTORISTA)
        db.add(Driver(nome="Outro",cpf="12345678902",telefone="11988888888",user=user));db.commit()
    token = client.post("/api/auth/login",json={"email":"other@example.com","senha":"Driver@123"}).json()["access_token"]
    other = {"Authorization":f"Bearer {token}"}
    assert client.get(f"/api/trips/{tid}", headers=other).status_code == 403
    assert client.get(url, headers=other).status_code == 403
    for action in ("start","finish","occurrence"):
        payload = {"motivo":"CLIENTE_FECHADO"} if action == "occurrence" else {}
        assert client.post(url+"/"+action, headers=other, json=payload).status_code == 403
        assert client.post(url+"/"+action, json=payload).status_code == 401
        assert client.post(url+"/"+action, headers=admin_headers,json=payload).status_code == 403
        assert client.post(f"/api/trips/9999/deliveries/{notes[0]['id']}/{action}", headers=driver_headers,json=payload).status_code == 404
        assert client.post(f"/api/trips/{tid}/deliveries/9999/{action}", headers=driver_headers,json=payload).status_code == 404
    assert client.get(url).status_code == 401
    assert client.get(f"/api/trips/9999/deliveries",headers=driver_headers).status_code == 404


@pytest.mark.parametrize("reason", ["CLIENTE_FECHADO","CLIENTE_RECUSOU","CLIENTE_AUSENTE","ENDERECO_NAO_LOCALIZADO","MERCADORIA_RECUSADA","OUTRO"])
def test_occurrence_reasons_and_validation(client,driver_headers,reason):
    tid,notes=prepare(client,driver_headers)
    url=f"/api/trips/{tid}/deliveries/{notes[0]['id']}"
    assert client.post(url+"/occurrence",headers=driver_headers,json={"motivo":reason,"observacao":"Detalhes"}).status_code == 409
    assert client.post(url+"/start",headers=driver_headers).status_code == 200
    assert client.post(url+"/occurrence",headers=driver_headers,json={"motivo":"INVALIDO"}).status_code == 422
    assert client.post(url+"/occurrence",headers=driver_headers,json={"motivo":"OUTRO","observacao":"   "}).status_code == 422
    assert client.post(url+"/occurrence",headers=driver_headers,json={"motivo":reason,"occurrence_at":"2000-01-01"}).status_code == 422
    result=client.post(url+"/occurrence",headers=driver_headers,json={"motivo":reason,"observacao":"Detalhes"})
    assert result.status_code == 200
    assert result.json()["status"] == "NAO_ENTREGUE"
    assert result.json()["delivered_at"] is None
    with SessionLocal() as db:
        occurrence=db.scalar(select(Occurrence))
        assert occurrence.invoice_id == notes[0]["id"]
        assert occurrence.driver_id is not None
        assert len(list(db.scalars(select(AuditLog).where(AuditLog.entidade == "TRIP_INVOICE")))) == 2


def test_concurrent_finish_is_atomic(client,driver_headers):
    tid,notes=prepare(client,driver_headers)
    url=f"/api/trips/{tid}/deliveries/{notes[0]['id']}"
    assert client.post(url+"/start",headers=driver_headers).status_code == 200
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:client.post(url+"/finish",headers=driver_headers),range(2)))
    assert sorted(r.status_code for r in results) == [200,409]
    with SessionLocal() as db:
        assert len(list(db.scalars(select(AuditLog).where(AuditLog.acao == "FINALIZAR_ENTREGA")))) == 1


def test_concurrent_occurrence_creates_one_record(client,driver_headers):
    tid,notes=prepare(client,driver_headers)
    url=f"/api/trips/{tid}/deliveries/{notes[0]['id']}"
    assert client.post(url+"/start",headers=driver_headers).status_code == 200
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:client.post(url+"/occurrence",headers=driver_headers,json={"motivo":"CLIENTE_FECHADO"}),range(2)))
    assert sorted(r.status_code for r in results) == [200,409]
    with SessionLocal() as db:
        assert len(list(db.scalars(select(Occurrence)))) == 1
        assert len(list(db.scalars(select(AuditLog).where(AuditLog.acao == "REGISTRAR_OCORRENCIA_ENTREGA")))) == 1


def test_invoice_from_another_trip_cannot_be_operated(client,driver_headers):
    first,notes=prepare(client,driver_headers)
    url=f"/api/trips/{first}/deliveries/{notes[0]['id']}"
    assert client.post(url+"/start",headers=driver_headers).status_code == 200
    assert client.post(url+"/finish",headers=driver_headers).status_code == 200
    assert client.post(f"/api/trips/{first}/finish",headers=driver_headers,json={"km_final":1000}).status_code == 200
    second,_=prepare(client,driver_headers)
    for action in ("start","finish","occurrence"):
        payload={"motivo":"CLIENTE_FECHADO"} if action == "occurrence" else {}
        assert client.post(f"/api/trips/{second}/deliveries/{notes[0]['id']}/{action}",headers=driver_headers,json=payload).status_code == 404
