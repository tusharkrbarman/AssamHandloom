from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request
from psycopg_pool import ConnectionPool

from .catalogue import CatalogueQuery, list_products
from .db import create_pool
from .orders import CartQuoteRequest, CheckoutRequest, create_order, get_order, quote_cart
from .payments import (
    PaymentSessionRequest,
    PaymentVerifyRequest,
    create_payment_session,
    handle_razorpay_webhook,
    razorpay_config,
    verify_payment,
)
from .settings import Settings


@asynccontextmanager
async def lifespan(application: FastAPI):
    database_url = Settings.from_env().database_url
    pool = create_pool(database_url) if database_url else None
    application.state.db_pool = pool
    if pool:
        pool.open(wait=False)
    try:
        yield
    finally:
        if pool:
            pool.close()


app = FastAPI(title="Luit & Loom API", version="0.1.0", lifespan=lifespan)


def _pool(request: Request) -> ConnectionPool:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(
            status_code=503,
            detail={"status": "unavailable", "database": "not_configured"},
        )
    return pool


def _require_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin or origin != str(request.base_url).rstrip("/"):
        raise HTTPException(
            status_code=403,
            detail={"code": "invalid_origin", "message": "The request origin is not allowed."},
        )


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Liveness probe: the process is running and can accept requests."""
    return {"status": "ok", "service": "api"}


@app.get("/ready", tags=["system"])
def ready(request: Request) -> dict[str, str]:
    """Readiness probe: the service can reach its PostgreSQL database."""
    pool = _pool(request)
    try:
        with pool.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail={"status": "unavailable", "database": "unavailable"},
        ) from error

    return {"status": "ok", "database": "ok"}


@app.get("/api/v1/catalog/products", tags=["catalogue"])
def catalogue_products(
    request: Request,
    search: Annotated[str | None, Query(max_length=160)] = None,
    q: Annotated[str | None, Query(max_length=160)] = None,
    silk_type: Annotated[str | None, Query(max_length=80)] = None,
    colour: Annotated[str | None, Query(max_length=80)] = None,
    occasion: Annotated[str | None, Query(max_length=80)] = None,
    available_only: bool = False,
    sort: str = "featured",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=24)] = 12,
    collection_slug: Annotated[str | None, Query(max_length=80)] = None,
) -> dict[str, object]:
    query = CatalogueQuery(
        search=search or q,
        silk_type=silk_type,
        colour=colour,
        occasion=occasion,
        available_only=available_only,
        sort=sort,
        page=page,
        page_size=page_size,
        collection_slug=collection_slug,
    )
    return list_products(_pool(request), query)


@app.post("/api/cart/quote", tags=["commerce"])
def cart_quote(payload: CartQuoteRequest, request: Request) -> dict[str, object]:
    _require_same_origin(request)
    return quote_cart(_pool(request), payload.items)


@app.post("/api/orders", status_code=201, tags=["commerce"])
def order_create(payload: CheckoutRequest, request: Request) -> dict[str, object]:
    _require_same_origin(request)
    settings = Settings.from_env()
    return create_order(_pool(request), payload, settings.cookie_signing_key)


@app.get("/api/orders/{order_id}", tags=["commerce"])
def order_read(
    order_id: str,
    request: Request,
    token: Annotated[str | None, Query(max_length=80)] = None,
    exp: Annotated[int | None, Query(ge=0)] = None,
    sig: Annotated[str | None, Query(max_length=128)] = None,
) -> dict[str, object]:
    settings = Settings.from_env()
    return get_order(_pool(request), order_id, token, exp, sig, settings.cookie_signing_key)


def _payment_config_or_error():
    config = razorpay_config(Settings.from_env())
    if config is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "payments_disabled", "message": "Online payments are not available yet."},
        )
    return config


@app.post("/api/payments/session", tags=["payments"])
def payment_session(payload: PaymentSessionRequest, request: Request) -> dict[str, object]:
    _require_same_origin(request)
    config = _payment_config_or_error()
    return create_payment_session(_pool(request), payload, config)


@app.post("/api/payments/verify", tags=["payments"])
def payment_verify(payload: PaymentVerifyRequest, request: Request) -> dict[str, str]:
    _require_same_origin(request)
    config = _payment_config_or_error()
    return verify_payment(_pool(request), payload, config)


@app.post("/api/webhooks/razorpay", tags=["payments"])
async def razorpay_webhook(request: Request) -> dict[str, bool]:
    config = _payment_config_or_error()
    return await handle_razorpay_webhook(_pool(request), request, config)
