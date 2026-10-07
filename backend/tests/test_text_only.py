import pytest
from pydantic import ValidationError

from app.schemas import ChecklistAnswerIn, OccurrenceCreate


def test_occurrence_requires_text_and_rejects_attachments():
    payload = {"trip_id": 1, "tipo": "PNEU", "descricao": "Pneu perdeu pressão"}
    assert OccurrenceCreate(**payload).descricao == payload["descricao"]
    with pytest.raises(ValidationError):
        OccurrenceCreate(**payload, attachments=[{"file_url": "/uploads/test.png"}])
    with pytest.raises(ValidationError):
        OccurrenceCreate(**{**payload, "descricao": ""})


def test_checklist_problem_requires_text_and_rejects_photo():
    payload = {"checklist_item_id": 1, "status": "PROBLEMA", "observacao": "Pneu desgastado"}
    assert ChecklistAnswerIn(**payload).observacao == payload["observacao"]
    with pytest.raises(ValidationError):
        ChecklistAnswerIn(**payload, foto_url="/uploads/test.png")
    with pytest.raises(ValidationError):
        ChecklistAnswerIn(**{**payload, "observacao": " "})


def test_upload_endpoints_are_unavailable(client, driver_headers):
    assert client.post("/api/uploads", headers=driver_headers, files={"file": ("test.png", b"test", "image/png")}).status_code == 404
    assert client.get("/uploads/test.png").status_code == 404
    schema = client.get("/openapi.json").json()
    assert "/api/uploads" not in schema["paths"]
    assert "attachments" not in schema["components"]["schemas"]["OccurrenceOut"]["properties"]
    assert "foto_url" not in schema["components"]["schemas"]["ChecklistAnswerOut"]["properties"]
