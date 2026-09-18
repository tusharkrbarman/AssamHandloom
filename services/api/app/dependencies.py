from fastapi import HTTPException, Request
from psycopg_pool import ConnectionPool


def request_pool(request: Request) -> ConnectionPool:
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        raise HTTPException(
            status_code=503,
            detail={"status": "unavailable", "database": "not_configured"},
        )
    return pool


def require_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin or origin != str(request.base_url).rstrip("/"):
        raise HTTPException(
            status_code=403,
            detail={"code": "invalid_origin", "message": "The request origin is not allowed."},
        )
