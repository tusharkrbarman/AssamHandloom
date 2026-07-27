from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse, Response

from app.catalog.routes import catalog_router
from app.config import Settings, get_settings
from app.health import health_router
from app.storefront.routes import storefront_router
from app.web import render

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the Luit & Loom ASGI application."""

    resolved = settings or get_settings()
    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await application.state.engine.dispose()

    app = FastAPI(title="Luit & Loom", version="0.1.0", lifespan=lifespan)
    app.state.settings = resolved
    app.state.engine = create_async_engine(resolved.database_url)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.include_router(health_router)
    app.include_router(storefront_router)
    app.include_router(catalog_router)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> Response:
        if exc.status_code == 404:
            return render(request, "errors/404.html", status_code=404)
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        return Response(str(exc.detail), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, _: Exception) -> Response:
        return render(request, "errors/500.html", status_code=500)

    return app
