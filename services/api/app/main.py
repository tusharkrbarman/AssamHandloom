from contextlib import asynccontextmanager
import logging
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row
from starlette.exceptions import HTTPException as StarletteHTTPException

from .catalogue import CatalogueQuery, list_products
from .admin import router as admin_router
from .dependencies import request_pool, require_same_origin
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
from .web import render_error, router as web_router


LOGGER = logging.getLogger(__name__)

SECURITY_HEADERS = {
    "content-security-policy": "default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; img-src 'self' data:; font-src 'self'; script-src 'self' https://checkout.razorpay.com; style-src 'self' 'unsafe-inline'; connect-src 'self' https://api.razorpay.com; frame-src https://api.razorpay.com https://checkout.razorpay.com",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "camera=(), microphone=(), geolocation=()",
    "strict-transport-security": "max-age=31536000",
}


class PathOnlyAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and len(record.args) >= 3:
            args = list(record.args)
            args[2] = str(args[2]).partition("?")[0]
            record.args = tuple(args)
        return True


logging.getLogger("uvicorn.access").addFilter(PathOnlyAccessFilter())


def apply_security_headers(response: Response) -> Response:
    response.headers.update(SECURITY_HEADERS)
    return response


@asynccontextmanager
async def lifespan(application: FastAPI):
    database_url = Settings.from_env().database_url
    pool = (
        ConnectionPool(
            conninfo=database_url,
            min_size=1,
            max_size=10,
            timeout=5,
            kwargs={"row_factory": dict_row},
            open=False,
        )
        if database_url
        else None
    )
    application.state.db_pool = pool
    if pool:
        pool.open(wait=False)
    try:
        yield
    finally:
        if pool:
            pool.close()


app = FastAPI(title="Luit & Loom API", version="0.1.0", lifespan=lifespan)
JSON_ERROR_PATHS = {"/health", "/ready"}


@app.middleware("http")
async def security_headers(request: Request, call_next) -> Response:
    return apply_security_headers(await call_next(request))

STATIC_DIR = Path(__file__).resolve().parents[3] / "app" / "static"
app.mount("/css", StaticFiles(directory=STATIC_DIR / "css"), name="css")
app.mount("/js", StaticFiles(directory=STATIC_DIR / "js"), name="js")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Liveness probe: the process is running and can accept requests."""
    return {"status": "ok", "service": "api"}


@app.get("/ready", tags=["system"])
def ready(request: Request) -> dict[str, str]:
    """Readiness probe: the service can reach its PostgreSQL database."""
    pool = request_pool(request)
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
    return list_products(request_pool(request), query)


@app.post("/api/cart/quote", tags=["commerce"])
def cart_quote(payload: CartQuoteRequest, request: Request) -> dict[str, object]:
    require_same_origin(request)
    return quote_cart(request_pool(request), payload.items)


@app.post("/api/orders", status_code=201, tags=["commerce"])
def order_create(payload: CheckoutRequest, request: Request) -> dict[str, object]:
    require_same_origin(request)
    settings = Settings.from_env()
    return create_order(request_pool(request), payload, settings.cookie_signing_key)


@app.get("/api/orders/{order_id}", tags=["commerce"])
def order_read(
    order_id: str,
    request: Request,
    token: Annotated[str | None, Query(max_length=80)] = None,
    exp: Annotated[int | None, Query(ge=0)] = None,
    sig: Annotated[str | None, Query(max_length=128)] = None,
) -> dict[str, object]:
    settings = Settings.from_env()
    return get_order(request_pool(request), order_id, token, exp, sig, settings.cookie_signing_key)


def _payment_config_or_error(settings: Settings | None = None):
    config = razorpay_config(settings or Settings.from_env())
    if config is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "payments_disabled", "message": "Online payments are not available yet."},
        )
    return config


@app.post("/api/payments/session", tags=["payments"])
def payment_session(payload: PaymentSessionRequest, request: Request) -> dict[str, object]:
    require_same_origin(request)
    settings = Settings.from_env()
    config = _payment_config_or_error(settings)
    return create_payment_session(request_pool(request), payload, config, settings.cookie_signing_key)


@app.post("/api/payments/verify", tags=["payments"])
def payment_verify(payload: PaymentVerifyRequest, request: Request) -> dict[str, str]:
    require_same_origin(request)
    settings = Settings.from_env()
    config = _payment_config_or_error(settings)
    return verify_payment(request_pool(request), payload, config, settings.cookie_signing_key)


@app.post("/api/webhooks/razorpay", tags=["payments"])
async def razorpay_webhook(request: Request) -> dict[str, bool]:
    config = _payment_config_or_error()
    return await handle_razorpay_webhook(request_pool(request), request, config)


@app.exception_handler(StarletteHTTPException)
def http_error(request: Request, error: StarletteHTTPException) -> Response:
    if request.url.path.startswith("/api/") or request.url.path in JSON_ERROR_PATHS:
        return JSONResponse(status_code=error.status_code, content={"detail": error.detail})
    return render_error(request, error.status_code, str(error.detail), str(uuid4()))


@app.exception_handler(Exception)
def unhandled_error(request: Request, _error: Exception) -> Response:
    request_id = str(uuid4())
    LOGGER.error(
        "Unhandled request error",
        extra={"request_id": request_id, "method": request.method, "path": request.url.path},
    )
    if request.url.path.startswith("/api/") or request.url.path in JSON_ERROR_PATHS:
        response = JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
        response.headers["x-request-id"] = request_id
    else:
        response = render_error(request, 500, "The request could not be completed.", request_id)
    return apply_security_headers(response)


app.include_router(admin_router)
app.include_router(web_router)
