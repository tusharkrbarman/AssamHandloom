from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.anyio
async def test_liveness_does_not_require_database(liveness_client):
    response = await liveness_client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "live"}


@pytest.mark.anyio
async def test_readiness_checks_postgresql(app_client):
    response = await app_client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "up"}


@pytest.mark.anyio
async def test_readiness_returns_503_when_the_database_is_unavailable() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://postgres@127.0.0.1:1/luit_loom_unreachable",
        secret_key="test-secret-key-that-is-long-enough",
        environment="test",
        public_base_url="http://testserver",
    )
    from app.main import create_app

    class FailedConnection:
        async def __aenter__(self) -> None:
            from sqlalchemy.exc import SQLAlchemyError

            raise SQLAlchemyError("database unavailable")

        async def __aexit__(self, *_: object) -> None:
            return None

    class FailedEngine:
        def connect(self) -> FailedConnection:
            return FailedConnection()

        async def dispose(self) -> None:
            return None

    app = create_app(settings)
    app.state.engine = FailedEngine()
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "database": "down"}


@pytest.mark.anyio
async def test_lifespan_disposes_the_application_engine() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://postgres@127.0.0.1:1/luit_loom_unreachable",
        secret_key="test-secret-key-that-is-long-enough",
        environment="test",
        public_base_url="http://testserver",
    )
    from app.main import create_app

    dispose = AsyncMock()

    app = create_app(settings)
    engine = type("DisposableEngine", (), {})()
    engine.dispose = dispose
    app.state.engine = engine

    async with app.router.lifespan_context(app):
        pass

    dispose.assert_awaited_once()


def test_settings_reject_empty_secret_key():
    with pytest.raises(ValidationError):
        Settings(
            database_url="postgresql+psycopg://luit:luit@localhost:5432/luit_loom",
            secret_key="",
            environment="development",
            public_base_url="http://localhost:8000",
            catalogue_preview_enabled=True,
        )


def test_settings_rejects_non_postgresql_database_outside_test_environment():
    with pytest.raises(ValidationError):
        Settings(
            database_url="sqlite+aiosqlite:///:memory:",
            secret_key="a" * 32,
            environment="development",
            public_base_url="http://localhost:8000",
            catalogue_preview_enabled=True,
        )


def test_settings_accepts_render_database_and_external_urls(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("DATABASE_URL", "postgresql://luit:secret@db:5432/luit_loom")
    monkeypatch.setenv("SECRET_KEY", "a" * 32)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("RENDER_EXTERNAL_URL", "https://luit-and-loom.onrender.com")
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)

    settings = Settings()

    assert settings.database_url == "postgresql+psycopg://luit:secret@db:5432/luit_loom"
    assert str(settings.public_base_url) == "https://luit-and-loom.onrender.com/"


def test_windows_uses_selector_event_loop_policy_for_psycopg():
    if sys.platform == "win32":
        assert isinstance(
            asyncio.get_event_loop_policy(),
            asyncio.WindowsSelectorEventLoopPolicy,
        )
