from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.catalog.routes import product_page
from app.db import get_session
from app.web import render

storefront_router = APIRouter()

_PAGES = {
    "artisans": {
        "title": "Artisans",
        "body": (
            "This directory is a sample preview. Verified maker profiles will be introduced only "
            "with consent and confirmed public details."
        ),
    },
    "our-story": {
        "title": "Our story",
        "body": (
            "Luit & Loom is a Phase 1 editorial catalogue exploring Assamese handloom with care. "
            "Orders and live inventory are not available yet."
        ),
    },
    "journal": {
        "title": "Journal",
        "body": (
            "Understanding the silks of Assam, how to identify authentic Muga silk, and how to "
            "care for a handwoven silk saree are planned editorial notes for this preview."
        ),
    },
    "silk-guide": {
        "title": "Silk guide",
        "body": (
            "Muga, Pat, and Eri have distinct qualities. This is introductory guidance, not a "
            "substitute for verified product facts."
        ),
    },
    "care": {
        "title": "Care guide",
        "body": (
            "Care instructions need verification for each real textile. Please request final "
            "guidance before purchase when checkout opens."
        ),
    },
    "shipping": {
        "title": "Shipping",
        "body": (
            "Shipping terms will be published before checkout opens. Phase 1 does not accept "
            "orders or promise dispatch times."
        ),
    },
    "returns": {
        "title": "Returns",
        "body": (
            "Returns information will be confirmed before checkout opens. No purchase flow is "
            "available in Phase 1."
        ),
    },
    "contact": {
        "title": "Contact",
        "body": (
            "This preview is not accepting orders or customer requests. Contact channels will "
            "be announced with the live catalogue."
        ),
    },
    "faq": {
        "title": "Frequently asked questions",
        "body": (
            "Phase 1 is a read-only preview. Prices, availability, people, and imagery are "
            "sample content until verified for a live release."
        ),
    },
}


@storefront_router.get("/")
async def home(request: Request, session: AsyncSession = Depends(get_session)) -> Response:
    _, page = await product_page(request, session)
    return render(request, "storefront/home.html", {"page": page, "home": True})


@storefront_router.get("/artisans")
@storefront_router.get("/our-story")
@storefront_router.get("/journal")
async def editorial_page(request: Request) -> Response:
    slug = request.url.path.lstrip("/")
    return render(request, "storefront/page.html", {"page_content": _PAGES[slug]})


@storefront_router.get("/pages/{slug}")
async def guidance_page(slug: str, request: Request) -> Response:
    page = _PAGES.get(slug)
    if page is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404)
    return render(request, "storefront/page.html", {"page_content": page})
