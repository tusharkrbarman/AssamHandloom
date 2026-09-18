from base64 import b64encode
from datetime import datetime, timezone
from json import JSONDecodeError, dumps, loads
from re import compile
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request as URLRequest, urlopen
from uuid import uuid4

from fastapi import HTTPException
from psycopg_pool import ConnectionPool

from .email import enqueue_order_email
from .payments import RazorpayConfig, razorpay_config
from .settings import Settings


RAZORPAY_REFUNDS_URL = "https://api.razorpay.com/v1/payments"
UUID_PATTERN = compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", flags=2)


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _post_refund(
    config: RazorpayConfig,
    provider_payment_id: str,
    amount_minor: int | None,
    receipt: str,
) -> tuple[str, str]:
    body = dumps({**({} if amount_minor is None else {"amount": amount_minor}), "receipt": receipt}).encode()
    request = URLRequest(
        f"{RAZORPAY_REFUNDS_URL}/{quote(provider_payment_id, safe='')}/refund",
        data=body,
        headers={
            "Authorization": "Basic " + b64encode(f"{config.key_id}:{config.key_secret}".encode()).decode(),
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            status_code = getattr(response, "status", None) or response.getcode()
            if not 200 <= status_code < 300:
                raise _error(502, "refund_failed", "The payment provider rejected the refund.")
            payload = loads(response.read())
    except HTTPException:
        raise
    except HTTPError as error:
        raise _error(502, "refund_failed", "The payment provider rejected the refund.") from error
    except (URLError, TimeoutError, OSError, JSONDecodeError, UnicodeDecodeError, TypeError, ValueError) as error:
        raise _error(502, "refund_provider_unavailable", "The payment provider could not be reached. Please try again shortly.") from error
    refund_id = payload.get("id") if isinstance(payload, dict) else None
    status = payload.get("status") if isinstance(payload, dict) else None
    if not isinstance(refund_id, str) or not refund_id.startswith("rfnd_") or not isinstance(status, str) or status.lower() not in {"processed", "pending", "failed"}:
        raise _error(502, "refund_failed", "The payment provider responded unexpectedly.")
    return refund_id, status.lower()


def refund_order_payment(
    pool: ConnectionPool,
    order_id: str,
    amount_minor: int | None = None,
    settings: Settings | None = None,
) -> dict[str, object]:
    order_id = order_id.strip().lower() if isinstance(order_id, str) else ""
    if not UUID_PATTERN.fullmatch(order_id):
        raise _error(404, "not_found", "That order could not be found.")
    config = razorpay_config(settings or Settings.from_env())
    if config is None:
        raise _error(503, "payments_disabled", "Online payments are not configured.")
    with pool.connection() as connection:
        with connection.transaction():
            # ponytail: keep one payment row locked across the provider call; move refunds to a durable job if volume demands it
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, provider_payment_id, amount_minor, currency
                    FROM order_payments
                    WHERE order_id = %s AND status = 'captured'
                    ORDER BY created_at DESC LIMIT 1
                    FOR UPDATE
                    """,
                    (order_id,),
                )
                payment = cursor.fetchone()
            if not payment or not payment["provider_payment_id"]:
                raise _error(409, "no_captured_payment", "There is no captured online payment to refund on this order.")
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COALESCE(SUM(CASE WHEN status <> 'failed' THEN amount_minor ELSE 0 END), 0) AS total, COUNT(*) AS attempts FROM order_refunds WHERE order_id = %s",
                    (order_id,),
                )
                totals = cursor.fetchone() or {"total": 0, "attempts": 0}
            refunded_total = int(totals["total"] or 0)
            remaining = int(payment["amount_minor"]) - refunded_total
            if remaining <= 0:
                raise _error(409, "already_refunded", "This payment has already been fully refunded.")
            target = remaining if amount_minor is None else amount_minor
            if isinstance(target, bool) or not isinstance(target, int) or target <= 0 or target > remaining:
                raise _error(422, "invalid_refund_amount", f"Refund amount must be between 1 and {remaining} paise.")
            attempt = int(totals["attempts"] or 0) + 1
            receipt = f"{order_id.replace('-', '')[:30]}-{attempt}"
            refund_id, status = _post_refund(
                config,
                str(payment["provider_payment_id"]),
                None if amount_minor is None else target,
                receipt,
            )
            now = _now()
            row = {
                "id": str(uuid4()),
                "orderId": order_id,
                "paymentId": payment["id"],
                "providerRefundId": refund_id,
                "amountMinor": target,
                "currency": payment["currency"],
                "status": status,
                "createdAt": now.isoformat(),
            }
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO order_refunds (
                      id, order_id, payment_id, provider_refund_id,
                      amount_minor, currency, status, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (row["id"], order_id, payment["id"], refund_id, target, payment["currency"], status, now),
                )
                if status in {"processed", "pending"}:
                    enqueue_order_email(connection, "order_refunded", order_id, at=now)
            return row
