# Routes

FastAPI decorator routing with server-rendered Jinja templates.

| URL | Entry | Template / response | Layout |
| --- | --- | --- | --- |
| `/` | `app/storefront/routes.py:home` | `storefront/home.html` | `base.html` |
| `/shop` | `app/catalog/routes.py:shop` | `catalog/list.html` | `base.html` |
| `/search` | `app/catalog/routes.py:shop` | `catalog/list.html` | `base.html` |
| `/collections` | `app/catalog/routes.py:collections` | `catalog/collections.html` | `base.html` |
| `/collections/{slug}` | `app/catalog/routes.py:collection` | `catalog/list.html` | `base.html` |
| `/products/{slug}` | `app/catalog/routes.py:product` | `catalog/product.html` | `base.html` |
| `/artisans` | `app/storefront/routes.py:editorial_page` | `storefront/page.html` | `base.html` |
| `/our-story` | `app/storefront/routes.py:editorial_page` | `storefront/page.html` | `base.html` |
| `/journal` | `app/storefront/routes.py:editorial_page` | `storefront/page.html` | `base.html` |
| `/pages/{slug}` | `app/storefront/routes.py:guidance_page` | `storefront/page.html` | `base.html` |

## Storefront router

Path: `app/storefront/routes.py`

```python
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
```

## Catalogue router

Path: `app/catalog/routes.py`

```python
@catalog_router.get("/shop")
@catalog_router.get("/search")
async def shop(request: Request, session: AsyncSession = Depends(get_session)) -> Response:
    query, page = await product_page(request, session)
    template = "components/product_grid.html" if is_htmx(request) else "catalog/list.html"
    return render(request, template, _listing_context(request, page, query))


@catalog_router.get("/collections")
async def collections(request: Request, session: AsyncSession = Depends(get_session)) -> Response:
    visible_collections = await _service(session).list_collections(
        request.app.state.settings.catalogue_preview_enabled
    )
    return render(request, "catalog/collections.html", {"collections": visible_collections})


@catalog_router.get("/collections/{slug}")
async def collection(
    slug: str, request: Request, session: AsyncSession = Depends(get_session)
) -> Response:
    query = replace(parse_product_query(request), collection_slug=slug)
    collections = await _service(session).list_collections(
        request.app.state.settings.catalogue_preview_enabled
    )
    selected = next((item for item in collections if item.slug == slug), None)
    if selected is None:
        raise HTTPException(status_code=404)
    page = await _service(session).list_products(
        query, request.app.state.settings.catalogue_preview_enabled
    )
    template = "components/product_grid.html" if is_htmx(request) else "catalog/list.html"
    context = _listing_context(request, page, query)
    context["collection"] = selected
    return render(request, template, context)


@catalog_router.get("/products/{slug}")
async def product(
    slug: str, request: Request, session: AsyncSession = Depends(get_session)
) -> Response:
    detail = await _service(session).get_product_by_slug(
        slug, request.app.state.settings.catalogue_preview_enabled
    )
    if detail is None:
        raise HTTPException(status_code=404)
    related = await _service(session).list_products(
        ProductListQuery(silk_types=(detail.silk_type,), page_size=4),
        request.app.state.settings.catalogue_preview_enabled,
    )
    return render(
        request,
        "catalog/product.html",
        {"product": detail, "related": [item for item in related.items if item.slug != slug][:3]},
    )
```
