from logging import INFO, LogRecord

from fastapi.testclient import TestClient

from app.main import PathOnlyAccessFilter, SECURITY_HEADERS, app


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


def test_access_log_filter_removes_the_query_string() -> None:
    record = LogRecord(
        "uvicorn.access",
        INFO,
        "",
        0,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:1234", "GET", "/orders/123?token=private&sig=secret", "1.1", 200),
        None,
    )

    assert PathOnlyAccessFilter().filter(record)
    assert record.args[2] == "/orders/123"
    assert "private" not in record.getMessage()
    assert "secret" not in record.getMessage()
    assert 'GET /orders/123 HTTP/1.1" 200' in record.getMessage()


def test_security_headers_cover_html_static_json_and_errors() -> None:
    client = TestClient(app)

    for path in ("/our-story", "/css/site.css", "/health", "/definitely-missing"):
        response = client.get(path)
        assert {name: response.headers[name] for name in SECURITY_HEADERS} == SECURITY_HEADERS


def test_security_headers_cover_unhandled_errors(monkeypatch) -> None:
    monkeypatch.setattr("app.web.request_pool", lambda _request: object())
    monkeypatch.setattr(
        "app.web.list_products",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("test failure")),
    )

    response = TestClient(app, raise_server_exceptions=False).get("/")

    assert response.status_code == 500
    assert {name: response.headers[name] for name in SECURITY_HEADERS} == SECURITY_HEADERS
