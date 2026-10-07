from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models import AuditLog, Driver, User
from app.models.enums import UserRole
from test_deliveries import prepare


def current(client, headers, tid):
    return client.get(f"/api/trips/{tid}", headers=headers).json()


def order(client, headers, tid, ids, revision=None):
    if revision is None:
        revision=current(client,headers,tid)["delivery_revision"]
    return client.put(f"/api/trips/{tid}/delivery-order",headers=headers,json={"invoice_ids":ids,"revision":revision})


def test_reorder_pending_persists_and_controls_operations(client,driver_headers,admin_headers):
    tid,notes=prepare(client,driver_headers,5)
    ids=[n["id"] for n in notes]
    new=[ids[2],ids[0],ids[4],ids[1],ids[3]]
    result=order(client,driver_headers,tid,new)
    assert result.status_code == 200,result.text
    assert [n["id"] for n in result.json()["notas"]] == new
    assert [n["position"] for n in result.json()["notas"]] == [1,2,3,4,5]
    assert [n["id"] for n in current(client,admin_headers,tid)["notas"]] == new
    assert [n["id"] for n in client.get(f"/api/trips/{tid}/deliveries",headers=driver_headers).json()] == new
    assert client.post(f"/api/trips/{tid}/deliveries/{ids[0]}/start",headers=driver_headers).status_code == 409
    assert client.post(f"/api/trips/{tid}/deliveries/{ids[2]}/start",headers=driver_headers).status_code == 200
    with SessionLocal() as db:
        log=db.scalar(select(AuditLog).where(AuditLog.acao == "REORDENAR_ENTREGAS"))
        assert log.detalhes["ordem_anterior"] == ids
        assert log.detalhes["ordem_nova"] == new
        assert log.user_id is not None


def test_postpone_active_and_resume_preserves_start_and_history(client,driver_headers):
    tid,notes=prepare(client,driver_headers,3)
    ids=[n["id"] for n in notes]
    root=f"/api/trips/{tid}/deliveries"
    started=client.post(f"{root}/{ids[0]}/start",headers=driver_headers).json()
    result=order(client,driver_headers,tid,[ids[1],ids[2],ids[0]])
    assert result.status_code == 200,result.text
    deferred=result.json()["notas"][-1]
    assert deferred["status"] == "PENDENTE"
    assert deferred["started_at"] == started["started_at"]
    assert deferred["occurrence_at"] is None
    assert deferred["delivered_at"] is None
    assert client.post(f"{root}/{ids[0]}/finish",headers=driver_headers).status_code == 409
    for id in ids[1:]:
        assert client.post(f"{root}/{id}/start",headers=driver_headers).status_code == 200
        assert client.post(f"{root}/{id}/finish",headers=driver_headers).status_code == 200
    resumed=client.post(f"{root}/{ids[0]}/start",headers=driver_headers)
    assert resumed.status_code == 200
    assert resumed.json()["started_at"] == started["started_at"]
    assert client.post(f"{root}/{ids[0]}/finish",headers=driver_headers).status_code == 200
    with SessionLocal() as db:
        log=db.scalar(select(AuditLog).where(AuditLog.acao == "ADIAR_ENTREGA"))
        assert log.detalhes["status_anterior"] == "EM_ENTREGA"
        assert log.detalhes["status_novo"] == "PENDENTE"


@pytest.mark.parametrize("action", ["finish", "occurrence"])
def test_treated_deliveries_stay_in_place(client,driver_headers,action):
    tid,notes=prepare(client,driver_headers,3)
    ids=[n["id"] for n in notes]
    root=f"/api/trips/{tid}/deliveries/{ids[0]}"
    assert client.post(root+"/start",headers=driver_headers).status_code == 200
    kwargs={"json":{"motivo":"CLIENTE_FECHADO"}} if action == "occurrence" else {}
    completed=client.post(root+"/"+action,headers=driver_headers,**kwargs).json()
    assert order(client,driver_headers,tid,[ids[1],ids[0],ids[2]]).status_code == 409
    result=order(client,driver_headers,tid,[ids[0],ids[2],ids[1]])
    assert result.status_code == 200
    assert result.json()["notas"][0] == completed


def test_invalid_order_stale_revision_and_idempotent_retry(client,driver_headers):
    tid,notes=prepare(client,driver_headers,3)
    ids=[n["id"] for n in notes]
    rev=current(client,driver_headers,tid)["delivery_revision"]
    for invalid in (ids[:2], [ids[0],ids[0],ids[2]], [ids[0],ids[1],99999]):
        assert order(client,driver_headers,tid,invalid).status_code == 422
    new=list(reversed(ids))
    saved=order(client,driver_headers,tid,new,rev)
    assert saved.status_code == 200
    assert order(client,driver_headers,tid,ids,rev).status_code == 409
    revision=saved.json()["delivery_revision"]
    repeated=order(client,driver_headers,tid,new,revision)
    assert repeated.status_code == 200
    assert repeated.json()["delivery_revision"] == revision
    with SessionLocal() as db:
        assert len(list(db.scalars(select(AuditLog).where(AuditLog.acao == "REORDENAR_ENTREGAS")))) == 1


def test_reorder_security_closed_route_and_missing_route(client,driver_headers,admin_headers):
    tid,notes=prepare(client,driver_headers,2)
    ids=[n["id"] for n in notes]
    with SessionLocal() as db:
        user=User(nome="Other",email="other@example.com",senha_hash=get_password_hash("Driver@123"),role=UserRole.MOTORISTA)
        db.add(Driver(nome="Other",cpf="12345678902",telefone="11999999999",user=user));db.commit()
    token=client.post("/api/auth/login",json={"email":"other@example.com","senha":"Driver@123"}).json()["access_token"]
    payload={"invoice_ids":ids,"revision":current(client,driver_headers,tid)["delivery_revision"]}
    url=f"/api/trips/{tid}/delivery-order"
    assert client.put(url,json=payload).status_code == 401
    assert client.put(url,headers=admin_headers,json=payload).status_code == 403
    assert client.put(url,headers={"Authorization":f"Bearer {token}"},json=payload).status_code == 403
    assert client.put("/api/trips/9999/delivery-order",headers=driver_headers,json=payload).status_code == 404
    for id in ids:
        root=f"/api/trips/{tid}/deliveries/{id}"
        assert client.post(root+"/start",headers=driver_headers).status_code == 200
        assert client.post(root+"/finish",headers=driver_headers).status_code == 200
    assert client.post(f"/api/trips/{tid}/finish",headers=driver_headers,json={"km_final":1100}).status_code == 200
    assert order(client,driver_headers,tid,ids).status_code == 409


def test_concurrent_order_changes_accept_one(client,driver_headers):
    tid,notes=prepare(client,driver_headers,3)
    ids=[n["id"] for n in notes]
    revision=current(client,driver_headers,tid)["delivery_revision"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda new:order(client,driver_headers,tid,new,revision),[list(reversed(ids)),[ids[1],ids[0],ids[2]]]))
    assert sorted(r.status_code for r in results) == [200,409]


def test_start_response_revision_can_be_used_to_reorder(client,driver_headers):
    vehicle=client.get("/api/vehicles?available=true",headers=driver_headers).json()["items"][0]
    trip=client.post("/api/trips",headers=driver_headers,json={"vehicle_id":vehicle["id"],"km_inicial":1000}).json()
    tid=trip["id"]
    cargo=client.put(f"/api/trips/{tid}/cargo",headers=driver_headers,json={"notas":[{"numero_nota":"1","volumes":1},{"numero_nota":"2","volumes":1}]}).json()
    assert cargo["delivery_revision"] == current(client,driver_headers,tid)["delivery_revision"]
    items=client.get("/api/checklist-items",headers=driver_headers).json()
    assert client.post(f"/api/trips/{tid}/checklist",headers=driver_headers,json={"answers":[{"checklist_item_id":i["id"],"status":"OK"} for i in items]}).status_code == 201
    started=client.post(f"/api/trips/{tid}/start",headers=driver_headers).json()
    assert started["delivery_revision"] == current(client,driver_headers,tid)["delivery_revision"]
    assert order(client,driver_headers,tid,[n["id"] for n in reversed(started["notas"])],started["delivery_revision"]).status_code == 200
