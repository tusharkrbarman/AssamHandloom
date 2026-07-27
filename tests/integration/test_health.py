from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.anyio
async def test_liveness_does_not_require_database(app_client):
    response = await app_client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "live"}


@pytest.mark.anyio
async def test_readiness_checks_postgresql(app_client):
    response = await app_client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "up"}


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
