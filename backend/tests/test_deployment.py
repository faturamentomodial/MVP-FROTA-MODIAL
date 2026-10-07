import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.spa import SPAStaticFiles


@pytest.mark.parametrize("url", ["postgres://fleet:pass@db/fleet", "postgresql://fleet:pass@db/fleet"])
def test_postgres_database_url_uses_installed_driver(url):
    assert Settings(database_url=url).database_url == "postgresql+psycopg://fleet:pass@db/fleet"


def test_spa_routes_keep_api_and_missing_assets_as_errors(tmp_path):
    (tmp_path / "index.html").write_text("<html>Frota</html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('frota')")
    app = FastAPI()

    @app.get("/api/status")
    def status():
        return {"ok": True}

    app.mount("/", SPAStaticFiles(directory=tmp_path, html=True))
    with TestClient(app) as client:
        assert client.get("/api/status").json() == {"ok": True}
        assert client.get("/assets/app.js").status_code == 200
        for path in ("/", "/login", "/admin/viagens/123"):
            response = client.get(path)
            assert response.status_code == 200
            assert "<html>Frota</html>" in response.text
        for path in ("/api/missing", "/api", "/uploads/missing.jpg", "/assets/missing.js", "/missing.svg"):
            assert client.get(path).status_code == 404
        assert client.post("/login").status_code == 405
