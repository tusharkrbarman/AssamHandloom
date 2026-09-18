from datetime import datetime, timezone
from re import compile
from uuid import uuid4

from fastapi import HTTPException
from psycopg_pool import ConnectionPool


UUID4_PATTERN = compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", flags=2)
MAX_DELTA = 2_147_483_647


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def validate_adjustment(delta: int, reason: str, idempotency_key: str) -> tuple[int, str, str]:
    if isinstance(delta, bool) or not isinstance(delta, int) or delta == 0 or abs(delta) > MAX_DELTA:
        raise _error(422, "invalid_inventory_delta", "Stock change must be a non-zero integer.")
    if not isinstance(reason, str):
        raise _error(422, "invalid_inventory_reason", "The stock adjustment is invalid.")
    if not isinstance(idempotency_key, str):
        raise _error(422, "invalid_idempotency_key", "The stock form has expired.")
    clean_reason = " ".join(reason.split())
    if len(clean_reason) < 3 or len(clean_reason) > 200:
        raise _error(422, "invalid_inventory_reason", "Reason must be 3 to 200 characters.")
    clean_key = idempotency_key.strip().lower()
    if not UUID4_PATTERN.fullmatch(clean_key):
        raise _error(422, "invalid_idempotency_key", "The stock form has expired.")
    return delta, clean_reason, clean_key


def _now() -> datetime:
    return datetime.now(timezone.utc)


def list_inventory(pool: ConnectionPool) -> list[dict[str, object]]:
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT variant.id AS variant_id, variant.sku,
                  product.title AS product_title, stock.quantity, stock.updated_at
                FROM inventory_items stock
                JOIN variants variant ON variant.id = stock.variant_id
                JOIN products product ON product.id = variant.product_id
                WHERE product.archived_at IS NULL
                ORDER BY product.title, variant.sku
                """,
                (),
            )
            rows = cursor.fetchall()
    return [
        {
            "variantId": row["variant_id"],
            "sku": row["sku"],
            "productTitle": row["product_title"],
            "quantity": int(row["quantity"]),
            "updatedAt": row.get("updated_at").isoformat() if hasattr(row.get("updated_at"), "isoformat") else row.get("updated_at"),
        }
        for row in rows
    ]


def adjust_inventory(
    pool: ConnectionPool,
    variant_id: str,
    delta: int,
    reason: str,
    idempotency_key: str,
    actor: str = "owner",
) -> dict[str, object]:
    clean_variant = variant_id.strip().lower() if isinstance(variant_id, str) else ""
    if not clean_variant or len(clean_variant) > 160 or "/" in clean_variant:
        raise _error(404, "not_found", "That inventory item could not be found.")
    delta, reason, idempotency_key = validate_adjustment(delta, reason, idempotency_key)
    now = _now()
    adjustment_id = str(uuid4())
    with pool.connection() as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, variant_id, delta, reason, idempotency_key, actor, created_at FROM inventory_adjustments WHERE idempotency_key = %s",
                    (idempotency_key,),
                )
                existing = cursor.fetchone()
                if existing:
                    return _adjustment_response(existing)
                cursor.execute(
                    "SELECT quantity FROM inventory_items WHERE variant_id = %s FOR UPDATE",
                    (clean_variant,),
                )
                stock = cursor.fetchone()
                if not stock:
                    raise _error(404, "not_found", "That inventory item could not be found.")
                # Re-check after the row lock so concurrent retries return the first write.
                cursor.execute(
                    "SELECT id, variant_id, delta, reason, idempotency_key, actor, created_at FROM inventory_adjustments WHERE idempotency_key = %s",
                    (idempotency_key,),
                )
                existing = cursor.fetchone()
                if existing:
                    return _adjustment_response(existing)
                if int(stock["quantity"]) + delta < 0:
                    raise _error(409, "insufficient_stock", "That change would make stock negative.")
                cursor.execute(
                    """
                    INSERT INTO inventory_adjustments (
                      id, variant_id, delta, reason, idempotency_key, actor, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (adjustment_id, clean_variant, delta, reason, idempotency_key, actor, now),
                )
                cursor.execute(
                    """
                    UPDATE inventory_items
                    SET quantity = quantity + %s, version = version + 1, updated_at = %s
                    WHERE variant_id = %s AND quantity + %s >= 0
                    """,
                    (delta, now, clean_variant, delta),
                )
                if cursor.rowcount != 1:
                    raise _error(409, "inventory_conflict", "Stock changed before this request completed.")
            return {
                "id": adjustment_id,
                "variantId": clean_variant,
                "delta": delta,
                "reason": reason,
                "idempotencyKey": idempotency_key,
                "actor": actor,
                "createdAt": now.isoformat(),
            }


def _adjustment_response(row: dict[str, object]) -> dict[str, object]:
    created = row["created_at"]
    return {
        "id": row["id"],
        "variantId": row["variant_id"],
        "delta": int(row["delta"]),
        "reason": row["reason"],
        "idempotencyKey": row["idempotency_key"],
        "actor": row["actor"],
        "createdAt": created.isoformat() if hasattr(created, "isoformat") else created,
    }
