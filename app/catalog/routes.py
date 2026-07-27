from __future__ import annotations

from dataclasses import asdict, replace
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.catalog.repository import CatalogRepository
from app.catalog.schemas import Page, ProductCard, ProductListQuery
from app.catalog.service import CatalogService
from app.db import get_session
from app.web import is_htmx, render

catalog_router = APIRouter()
_SORTS = {"featured", "newest", "price_asc", "price_desc"}


def _normalise_search(value: str | None) -> str | None:
    normalised = " ".join((value or "").split())
    return normalised or None


def _positive_int(value: str | None, default: int) -> int:
    try:
        return max(1, int(value)) if value is not None else default
    except ValueError:
        return default


def parse_product_query(request: Request, *, api: bool = False) -> ProductListQuery:
    """Parse stable public catalogue query parameters from one URL."""

    sort = request.query_params.get("sort", "featured")
    if sort not in _SORTS:
        if api:
            raise HTTPException(status_code=422, detail="Invalid sort value")
        sort = "featured"
    page_size = min(24, _positive_int(request.query_params.get("page_size"), 12))
    return ProductListQuery(
        search=_normalise_search(
            request.query_params.get("search") or request.query_params.get("q")
        ),
        silk_types=tuple(request.query_params.getlist("silk_type")),
        colours=tuple(request.query_params.getlist("colour")),
        occasions=tuple(request.query_params.getlist("occasion")),
        available_only=request.query_params.get("available_only", "").lower()
        in {"1", "true", "yes", "on"},
        sort=sort,  # type: ignore[arg-type]
        page=_positive_int(request.query_params.get("page"), 1),
        page_size=page_size,
    )


def _service(session: AsyncSession) -> CatalogService:
    return CatalogService(CatalogRepository(session))


def _page_payload(page: Page[ProductCard]) -> dict[str, object]:
    return {
        "items": [asdict(card) for card in page.items],
        "page": page.page,
        "page_size": page.page_size,
        "total": page.total,
        "pages": page.total_pages,
    }


def _listing_context(
    request: Request, page: Page[ProductCard], query: ProductListQuery
) -> dict[str, object]:
    """Provide one stable, shareable context for full and HTMX catalogue renders."""

    pairs = [(key, value) for key, value in request.query_params.multi_items() if key != "page"]
    pagination_query = urlencode(pairs)
    return {
        "page": page,
        "query": query,
        "pagination_query": f"{pagination_query}&" if pagination_query else "",
    }


async def product_page(
    request: Request, session: AsyncSession, *, api: bool = False
) -> tuple[ProductListQuery, Page[ProductCard]]:
    query = parse_product_query(request, api=api)
    page = await _service(session).list_products(
        query, request.app.state.settings.catalogue_preview_enabled
    )
    return query, page


@catalog_router.get("/api/v1/catalog/products")
async def product_api(
    request: Request, session: AsyncSession = Depends(get_session)
) -> dict[str, object]:
    _, page = await product_page(request, session, api=True)
    return _page_payload(page)


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
