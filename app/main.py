from __future__ import annotations

import asyncio
import sys

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import Settings, get_settings
from app.health import health_router

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the Luit & Loom ASGI application."""

    resolved = settings or get_settings()
    app = FastAPI(title="Luit & Loom", version="0.1.0")
    app.state.settings = resolved
    app.state.engine = create_async_engine(resolved.database_url)
    app.include_router(health_router)
    return app
