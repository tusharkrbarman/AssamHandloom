from base64 import b64encode
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from hmac import compare_digest, new
from json import JSONDecodeError, dumps, loads
from re import compile
from urllib.error import HTTPError, URLError
from urllib.request import Request as URLRequest, urlopen
from uuid import uuid4

from fastapi import HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field
from psycopg_pool import ConnectionPool

from .email import enqueue_order_email
from .links import verify_order_link
from .settings import Settings


RAZORPAY_ORDERS_URL = "https://api.razorpay.com/v1/orders"
UUID_PATTERN = compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", flags=2)


@dataclass(frozen=True, slots=True)
class RazorpayConfig:
    key_id: str
    key_secret: str
    webhook_secret: str


class PaymentSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    order_id: str = Field(alias="orderId")
    token: str | None = None
    exp: int | None = Field(default=None, ge=0)
    sig: str | None = Field(default=None, max_length=128)


class PaymentVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    order_id: str = Field(alias="orderId")
    token: str | None = None
    exp: int | None = Field(default=None, ge=0)
    sig: str | None = Field(default=None, max_length=128)
    razorpay_order_id: str = Field(alias="razorpayOrderId")
    razorpay_payment_id: str = Field(alias="razorpayPaymentId")
    signature: str


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def razorpay_config(settings: Settings | None = None) -> RazorpayConfig | None:
    values = settings or Settings.from_env()
    key_id = (values.razorpay_key_id or "").strip()
    key_secret = (values.razorpay_key_secret or "").strip()
    webhook_secret = (values.razorpay_webhook_secret or "").strip()
    if not key_id or not key_secret or not webhook_secret:
        return None
    return RazorpayConfig(key_id, key_secret, webhook_secret)


def _uuid(value: str, code: str = "not_found") -> str:
    clean = value.strip()
    if not UUID_PATTERN.fullmatch(clean):
        raise _error(404, code, "That order could not be found.")
    return clean.lower()


def _provider_id(value: str, prefix: str, code: str) -> str:
    clean = value.strip()
    if not clean.startswith(prefix) or len(clean) > 80:
        raise _error(422, code, "The payment reference is incomplete.")
    return clean


def _payment_access(
    order_id: str,
    token: str | None,
    expires_at: int | None,
    signature: str | None,
    signing_secret: str | None,
) -> tuple[str, str | None]:
    clean_order_id = _uuid(order_id)
    if token:
        return clean_order_id, _uuid(token)
    if signing_secret and verify_order_link(clean_order_id, expires_at, signature, signing_secret):
        return clean_order_id, None
    raise _error(404, "not_found", "That order could not be found.")


def _hex_hmac(payload: bytes, secret: str) -> str:
    return new(secret.encode(), payload, sha256).hexdigest()


def payment_signature(provider_order_id: str, provider_payment_id: str, secret: str) -> str:
    return _hex_hmac(f"{provider_order_id}|{provider_payment_id}".encode(), secret)


def webhook_signature(payload: bytes, secret: str) -> str:
    return _hex_hmac(payload, secret)


def _valid_signature(expected: str, received: str) -> bool:
    value = received.strip().lower()
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        return False
    return compare_digest(expected, value)


def _provider_error() -> HTTPException:
    return _error(
        502,
        "payment_provider_unavailable",
        "The payment provider could not be reached. Please try again shortly.",
    )


def _create_provider_order(config: RazorpayConfig, order: dict[str, object]) -> str:
    body = dumps(
        {
            "amount": int(order["total_minor"]),
            "currency": str(order["currency"]),
            "receipt": str(order["id"]),
            "notes": {"order_id": str(order["id"])},
        }
    ).encode()
    request = URLRequest(
        RAZORPAY_ORDERS_URL,
        data=body,
        headers={
            "Authorization": "Basic " + b64encode(f"{config.key_id}:{config.key_secret}".encode()).decode(),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            if not 200 <= status < 300:
                raise _provider_error()
            payload = loads(response.read())
    except HTTPException:
        raise
    except (
        HTTPError,
        URLError,
        TimeoutError,
        OSError,
        JSONDecodeError,
        UnicodeDecodeError,
        TypeError,
        ValueError,
    ) as error:
        raise _provider_error() from error
    provider_order_id = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(provider_order_id, str) or not provider_order_id.startswith("order_"):
        raise _provider_error()
    return provider_order_id


def _expire_pending_order(connection, order_id: str, at: datetime) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE inventory_reservations
            SET state = 'released'
            WHERE order_id = %s AND state = 'active'
            """,
            (order_id,),
        )
        cursor.execute(
            """
            UPDATE orders
            SET status = 'expired', updated_at = %s
            WHERE id = %s AND status = 'pending'
              AND NOT EXISTS (
                SELECT 1 FROM inventory_reservations
                WHERE order_id = %s AND state = 'active'
              )
            """,
            (at, order_id, order_id),
        )


def _load_payable_order(connection, order_id: str, token: str | None, lock: bool) -> dict[str, object]:
    lock_clause = " FOR UPDATE" if lock else ""
    now = _now()
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT order_record.id, order_record.status, order_record.total_minor,
              order_record.currency,
              CASE WHEN EXISTS (
                SELECT 1 FROM inventory_reservations reservation
                WHERE reservation.order_id = order_record.id
              ) AND NOT EXISTS (
                SELECT 1
                FROM inventory_reservations reservation
                LEFT JOIN inventory_items stock ON stock.variant_id = reservation.variant_id
                WHERE reservation.order_id = order_record.id
                  AND (
                    reservation.state <> 'active'
                    OR reservation.expires_at <= %s
                    OR stock.variant_id IS NULL
                    OR stock.quantity < reservation.quantity
                  )
              ) THEN TRUE ELSE FALSE END AS reservations_payable
            FROM orders order_record
            WHERE order_record.id = %s AND (%s IS NULL OR order_record.token = %s)
            {lock_clause}
            """,
            (now, order_id, token, token),
        )
        order = cursor.fetchone()
    if not order:
        raise _error(404, "not_found", "That order could not be found.")
    if order["status"] != "pending":
        raise _error(409, "payment_not_pending", "This order is not awaiting payment.")
    if not order["reservations_payable"]:
        _expire_pending_order(connection, str(order["id"]), now)
        raise _error(
            409,
            "reservation_expired",
            "This reservation has expired. Please place the order again before paying.",
        )
    return order


def create_payment_session(
    pool: ConnectionPool,
    payload: PaymentSessionRequest,
    config: RazorpayConfig,
    signing_secret: str | None,
) -> dict[str, object]:
    order_id, token = _payment_access(payload.order_id, payload.token, payload.exp, payload.sig, signing_secret)
    with pool.connection() as connection:
        with connection.transaction():
            order = _load_payable_order(connection, order_id, token, lock=True)
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, provider_order_id, amount_minor, currency
                    FROM order_payments
                    WHERE order_id = %s AND status = 'created'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (order["id"],),
                )
                payment = cursor.fetchone()
            if payment and int(payment["amount_minor"]) == int(order["total_minor"]) and payment["currency"] == order["currency"]:
                provider_order_id = str(payment["provider_order_id"])
                amount_minor = int(payment["amount_minor"])
                currency = str(payment["currency"])
            else:
                # ponytail: hold the order lock across one provider call; move to an outbox if checkout concurrency demands it
                provider_order_id = _create_provider_order(config, order)
                amount_minor = int(order["total_minor"])
                currency = str(order["currency"])
                now = _now()
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO order_payments (
                          id, order_id, provider, provider_order_id, provider_payment_id,
                          amount_minor, currency, status, created_at, updated_at
                        ) VALUES (%s, %s, 'razorpay', %s, NULL, %s, %s, 'created', %s, %s)
                        """,
                        (
                            str(uuid4()),
                            order["id"],
                            provider_order_id,
                            amount_minor,
                            currency,
                            now,
                            now,
                        ),
                    )
    return {
        "keyId": config.key_id,
        "razorpayOrderId": provider_order_id,
        "amountMinor": amount_minor,
        "currency": currency,
    }


def _payment_for_checkout(
    connection,
    order_id: str,
    token: str | None,
    provider_order_id: str,
) -> dict[str, object]:
    provider_order_id = _provider_id(provider_order_id, "order_", "invalid_callback")
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT payment.id, payment.order_id, payment.provider_order_id,
              payment.provider_payment_id, payment.amount_minor, payment.currency,
              payment.status
            FROM order_payments payment
            JOIN orders order_record ON order_record.id = payment.order_id
            WHERE payment.provider_order_id = %s
              AND order_record.id = %s
              AND (%s IS NULL OR order_record.token = %s)
            LIMIT 1
            """,
            (provider_order_id, order_id, token, token),
        )
        payment = cursor.fetchone()
    if not payment:
        raise _error(404, "payment_not_found", "That payment reference could not be found.")
    return payment


def _reservation_rows(connection, order_id: str) -> list[dict[str, object]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT reservation.id, reservation.variant_id, reservation.quantity,
              reservation.state, reservation.expires_at, stock.quantity AS stock_quantity
            FROM inventory_reservations reservation
            JOIN inventory_items stock ON stock.variant_id = reservation.variant_id
            WHERE reservation.order_id = %s
            ORDER BY reservation.variant_id
            FOR UPDATE OF reservation, stock
            """,
            (order_id,),
        )
        return list(cursor.fetchall())


def _settle_reserved_order_locked(
    connection,
    order: dict[str, object],
    actor: str,
    reservations: list[dict[str, object]] | None = None,
    at: datetime | None = None,
) -> str:
    """Consume an order's active reservations and mark it paid.

    The caller must hold the order row lock and be inside a transaction.
    """
    status = str(order["status"])
    if status in {"paid", "fulfilled"}:
        return "already_paid"
    if status != "pending":
        return "expired"

    now = at or _now()
    rows = reservations if reservations is not None else _reservation_rows(connection, str(order["id"]))
    if not rows or any(
        row["state"] != "active"
        or row["expires_at"] <= now
        or int(row["stock_quantity"]) < int(row["quantity"])
        for row in rows
    ):
        _expire_pending_order(connection, str(order["id"]), now)
        return "expired"

    with connection.cursor() as cursor:
        for row in rows:
            quantity = int(row["quantity"])
            cursor.execute(
                """
                INSERT INTO inventory_adjustments (
                  id, variant_id, delta, reason, idempotency_key, actor, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (idempotency_key) DO NOTHING
                """,
                (
                    f"sale:{row['id']}",
                    row["variant_id"],
                    -quantity,
                    f"Order {order['id']} paid",
                    f"sale:{row['id']}",
                    actor,
                    now,
                ),
            )
            if cursor.rowcount == 0:
                continue
            cursor.execute(
                """
                UPDATE inventory_items
                SET quantity = quantity - %s, version = version + 1, updated_at = %s
                WHERE variant_id = %s AND quantity >= %s
                """,
                (quantity, now, row["variant_id"], quantity),
            )
            if cursor.rowcount != 1:
                raise _error(409, "inventory_conflict", "Stock changed while confirming this payment.")
        cursor.execute(
            "UPDATE inventory_reservations SET state = 'consumed' WHERE order_id = %s AND state = 'active'",
            (order["id"],),
        )
        cursor.execute(
            "UPDATE orders SET status = 'paid', updated_at = %s WHERE id = %s AND status = 'pending'",
            (now, order["id"]),
        )
        if cursor.rowcount != 1:
            raise _error(409, "order_conflict", "The order changed before payment completed.")
        enqueue_order_email(connection, "order_paid", str(order["id"]), at=now)
    return "paid"


def settle_reserved_order(
    pool: ConnectionPool,
    order_id: str,
    actor: str = "owner",
) -> str:
    """Settle a pending order without a provider payment (owner action)."""
    order_id = _uuid(order_id)
    with pool.connection() as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, status FROM orders WHERE id = %s FOR UPDATE",
                    (order_id,),
                )
                order = cursor.fetchone()
            if not order:
                raise _error(404, "not_found", "That order could not be found.")
            return _settle_reserved_order_locked(connection, order, actor)


def apply_captured_payment(
    pool: ConnectionPool,
    payment_id: str,
    provider_payment_id: str,
    actor: str = "payment",
) -> str:
    provider_payment_id = _provider_id(provider_payment_id, "pay_", "invalid_callback")
    with pool.connection() as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, order_id, provider_payment_id, status
                    FROM order_payments
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (payment_id,),
                )
                payment = cursor.fetchone()
            if not payment:
                raise _error(404, "payment_not_found", "That payment reference could not be found.")
            already_captured = payment["status"] == "captured"
            if already_captured:
                if payment["provider_payment_id"] != provider_payment_id:
                    raise _error(409, "payment_conflict", "This order was already paid with a different payment.")
            else:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE order_payments
                        SET provider_payment_id = %s, status = 'captured',
                          failure_reason = NULL, updated_at = %s
                        WHERE id = %s AND status <> 'captured'
                        """,
                        (provider_payment_id, _now(), payment_id),
                    )

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id, status FROM orders WHERE id = %s FOR UPDATE",
                    (payment["order_id"],),
                )
                order = cursor.fetchone()
            if not order:
                raise _error(404, "not_found", "That order could not be found.")
            if order["status"] in {"paid", "fulfilled"}:
                return "already_captured"
            if order["status"] != "pending":
                return "requires_review"

            outcome = _settle_reserved_order_locked(
                connection,
                order,
                actor,
                reservations=_reservation_rows(connection, str(order["id"])),
            )
            if outcome == "expired":
                return "requires_review"
    return "already_captured" if already_captured else "captured"


def verify_payment(
    pool: ConnectionPool,
    payload: PaymentVerifyRequest,
    config: RazorpayConfig,
    signing_secret: str | None,
) -> dict[str, str]:
    order_id, token = _payment_access(payload.order_id, payload.token, payload.exp, payload.sig, signing_secret)
    with pool.connection() as connection:
        payment = _payment_for_checkout(
            connection,
            order_id,
            token,
            payload.razorpay_order_id,
        )
    expected = payment_signature(payload.razorpay_order_id.strip(), payload.razorpay_payment_id.strip(), config.key_secret)
    if not _valid_signature(expected, payload.signature):
        raise _error(
            400,
            "invalid_payment_signature",
            "We could not confirm this payment. No money was captured by us.",
        )
    outcome = apply_captured_payment(pool, str(payment["id"]), payload.razorpay_payment_id)
    if outcome == "requires_review":
        raise _error(
            409,
            "payment_requires_review",
            "Payment was received after the reservation expired. The store owner will review or refund it.",
        )
    return {"status": "paid"}


def _event_record(event: object, *keys: str) -> dict[str, object] | None:
    current: object = event
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current if isinstance(current, dict) else None


def _text(record: dict[str, object] | None, key: str) -> str:
    value = record.get(key) if record else None
    return value.strip() if isinstance(value, str) else ""


def _minor_amount(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    return int(value)


def _process_razorpay_webhook(
    pool: ConnectionPool,
    raw: bytes,
    received: str,
    config: RazorpayConfig,
) -> dict[str, bool]:
    if not _valid_signature(webhook_signature(raw, config.webhook_secret), received):
        raise _error(400, "invalid_webhook_signature", "Webhook signature verification failed.")
    try:
        event = loads(raw)
    except (JSONDecodeError, UnicodeDecodeError, TypeError) as error:
        raise _error(400, "invalid_webhook_payload", "The webhook payload could not be read.") from error
    if not isinstance(event, dict):
        raise _error(400, "invalid_webhook_payload", "The webhook payload could not be read.")

    event_type = event.get("event") if isinstance(event.get("event"), str) else ""
    payment_entity = _event_record(event, "payload", "payment", "entity")
    if event_type == "payment.failed":
        provider_order_id = _text(payment_entity, "order_id")
        if provider_order_id.startswith("order_"):
            with pool.connection() as connection:
                with connection.transaction():
                    at = _now()
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            UPDATE order_payments
                            SET status = 'failed', failure_reason = %s, updated_at = %s
                            WHERE provider_order_id = %s AND status <> 'captured'
                            RETURNING order_id
                            """,
                            (_text(payment_entity, "error_description") or "Payment failed.", at, provider_order_id),
                        )
                        payment = cursor.fetchone()
                    if payment:
                        enqueue_order_email(connection, "payment_failed", str(payment["order_id"]), at=at)
        return {"received": True}

    if event_type not in {"payment.captured", "order.paid"}:
        return {"received": True}

    order_entity = _event_record(event, "payload", "order", "entity")
    source = payment_entity or order_entity
    provider_payment_id = _text(payment_entity, "id")
    provider_order_id = _text(source, "order_id") or (
        _text(source, "id") if event_type == "order.paid" else ""
    )
    if not provider_payment_id.startswith("pay_") or not provider_order_id.startswith("order_"):
        return {"received": True}
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, amount_minor, currency
                FROM order_payments
                WHERE provider_order_id = %s
                LIMIT 1
                """,
                (provider_order_id,),
            )
            payment = cursor.fetchone()
    if not payment:
        return {"received": True}
    amount = _minor_amount(source.get("amount") if source else None)
    currency = _text(source, "currency").upper()
    if amount != int(payment["amount_minor"]) or currency != payment["currency"]:
        raise _error(409, "payment_amount_mismatch", "The reported payment does not match this order.")
    outcome = apply_captured_payment(pool, str(payment["id"]), provider_payment_id, actor="webhook")
    if outcome == "requires_review":
        raise _error(
            409,
            "payment_requires_review",
            "Payment was received after the reservation expired. The store owner will review or refund it.",
        )
    return {"received": True}


async def handle_razorpay_webhook(
    pool: ConnectionPool,
    request: Request,
    config: RazorpayConfig,
) -> dict[str, bool]:
    raw = await request.body()
    received = request.headers.get("x-razorpay-signature", "")
    return await run_in_threadpool(_process_razorpay_webhook, pool, raw, received, config)
