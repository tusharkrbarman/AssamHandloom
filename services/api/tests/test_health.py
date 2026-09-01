from fastapi.testclient import TestClient

from app.main import app


def test_health_is_a_liveness_probe() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}


def test_ready_requires_database_configuration(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    response = TestClient(app).get("/ready")

    assert response.status_code == 503
    assert response.json()["detail"]["database"] == "not_configured"


def test_catalogue_requires_database_configuration(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    response = TestClient(app).get("/api/v1/catalog/products")

    assert response.status_code == 503
    assert response.json()["detail"]["database"] == "not_configured"


def test_catalogue_rejects_page_size_above_api_limit() -> None:
    response = TestClient(app).get("/api/v1/catalog/products?page_size=25")

    assert response.status_code == 422


def test_static_css_asset_is_served() -> None:
    response = TestClient(app).get("/css/site.css")

    assert response.status_code == 200
