from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator, Generator

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import Settings
from app.db import get_session
from app.main import create_app


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


def _require_postgresql_test_url() -> str:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.fail("TEST_DATABASE_URL must point to a PostgreSQL database")
    if not database_url.startswith("postgresql"):
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL")
    return database_url


def _url_for_schema(database_url: str, schema_name: str) -> str:
    url = make_url(database_url)
    return url.update_query_dict({"options": f"-csearch_path={schema_name}"}).render_as_string(
        hide_password=False
    )


@pytest.fixture(scope="session")
def test_database_url() -> Generator[str, None, None]:
    database_url = _require_postgresql_test_url()
    schema_name = f"test_{uuid.uuid4().hex}"
    admin_engine = create_async_engine(database_url)

    async def create_schema() -> None:
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))

    asyncio.run(create_schema())
    schema_url = _url_for_schema(database_url, schema_name)
    alembic_config = Config("alembic.ini")
    alembic_config.set_main_option("sqlalchemy.url", schema_url.replace("%", "%%"))
    command.upgrade(alembic_config, "head")

    try:
        yield schema_url
    finally:

        async def drop_schema() -> None:
            async with admin_engine.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
            await admin_engine.dispose()

        asyncio.run(drop_schema())


@pytest.fixture
async def liveness_client() -> AsyncGenerator[AsyncClient, None]:
    settings = Settings(
        database_url="postgresql+psycopg://postgres@127.0.0.1:1/luit_loom_unreachable",
        secret_key="test-secret-key-that-is-long-enough",
        environment="test",
        public_base_url="http://testserver",
        catalogue_preview_enabled=True,
    )
    app = create_app(settings)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    await app.state.engine.dispose()


@pytest.fixture
async def app_client(test_database_url: str) -> AsyncGenerator[AsyncClient, None]:
    settings = Settings(
        database_url=test_database_url,
        secret_key="test-secret-key-that-is-long-enough",
        environment="test",
        public_base_url="http://testserver",
        catalogue_preview_enabled=True,
    )
    app = create_app(settings)

    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        async with AsyncSession(app.state.engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    await app.state.engine.dispose()
