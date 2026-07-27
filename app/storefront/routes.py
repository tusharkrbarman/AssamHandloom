from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.catalog.routes import product_page
from app.db import get_session
from app.web import render

storefront_router = APIRouter()


@storefront_router.get("/")
async def home(request: Request, session: AsyncSession = Depends(get_session)) -> Response:
    _, page = await product_page(request, session)
    return render(request, "storefront/home.html", {"page": page})
