from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

health_router = APIRouter(prefix="/health", tags=["health"])


@health_router.get("/live")
async def live() -> dict[str, str]:
    """Report process liveness without checking external dependencies."""

    return {"status": "live"}


@health_router.get("/ready", response_model=None)
async def ready(request: Request) -> dict[str, str] | JSONResponse:
    """Report readiness after proving PostgreSQL accepts a simple query."""

    try:
        async with request.app.state.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "down"},
        )

    return {"status": "ready", "database": "up"}
