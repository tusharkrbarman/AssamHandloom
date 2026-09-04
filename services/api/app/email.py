from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import escape
from json import dumps
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request as URLRequest, urlopen
from uuid import uuid4

from psycopg_pool import ConnectionPool

from .catalogue import format_money
from .links import create_order_link
from .settings import Settings


RESEND_ENDPOINT = "https://api.resend.com/emails"
MAX_ATTEMPTS = 5
BACKOFF_CAP_MINUTES = 60
EMAIL_KINDS = {
    "order_confirmation",
    "order_paid",
    "payment_failed",
    "order_shipped",
    "order_cancelled",
    "order_refunded",
}


@dataclass(frozen=True, slots=True)
class MailConfig:
    api_key: str
    from_email: str
    base_url: str = ""


@dataclass(frozen=True, slots=True)
class OrderEmail:
    subject: str
    html: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def mail_config(settings: Settings | None = None) -> MailConfig | None:
    values = settings or Settings.from_env()
    api_key = (values.resend_api_key or "").strip()
    from_email = (values.mail_from or "").strip()
    if not api_key or not from_email:
        return None
    return MailConfig(api_key, from_email, (values.public_base_url or "").strip())


def _short_reference(order_id: str) -> str:
    return order_id[:8].upper()


def _event_copy(kind: str, name: str, city: str) -> tuple[str, str]:
    reference = ""
    if kind == "order_confirmation":
        return (
            f"Your Luit & Loom order {reference}",
            f"Hello {name}, thank you for your order. We have reserved your weaves and will confirm once payment is complete.",
        )
    if kind == "order_paid":
        return (
            f"Payment received — Luit & Loom order {reference}",
            f"Hello {name}, we have received your payment. Your weaves are confirmed and will be prepared for dispatch.",
        )
    if kind == "payment_failed":
        return (
            f"Payment update — Luit & Loom order {reference}",
            f"Hello {name}, we could not confirm payment for your order. Your reservation remains available while the payment window is open.",
        )
    if kind == "order_shipped":
        return (
            f"Your Luit & Loom order {reference} has shipped",
            f"Hello {name}, your order has been dispatched and is on its way to {city}. Thank you for supporting handwoven silk.",
        )
    if kind == "order_cancelled":
        return (
            f"Your Luit & Loom order {reference} was cancelled",
            f"Hello {name}, your order has been cancelled. If a payment was captured, the refund will be handled according to our refund policy.",
        )
    if kind == "order_refunded":
        return (
            f"Refund issued — Luit & Loom order {reference}",
            f"Hello {name}, a refund has been issued for your order. Please allow your payment provider's normal processing time.",
        )
    raise ValueError(f"unsupported_email_kind:{kind}")


def build_order_email(
    kind: str,
    order: Mapping[str, object],
    items: list[Mapping[str, object]],
    *,
    base_url: str = "",
    signing_secret: str | None = None,
) -> OrderEmail:
    if kind not in EMAIL_KINDS:
        raise ValueError(f"unsupported_email_kind:{kind}")
    order_id = str(order["id"])
    reference = _short_reference(order_id)
    name = escape(str(order.get("ship_name", "there")))
    city = escape(str(order.get("ship_city", "your address")))
    subject, intro = _event_copy(kind, name, city)
    subject = subject.replace("order ", f"order {reference}", 1) if "order " in subject else subject.replace(" —", f" {reference} —", 1)
    rows_html = "".join(
        f"<tr><td style=\"padding:6px 12px 6px 0\">{escape(str(item['product_title']))} · {escape(str(item['variant_title']))}</td>"
        f"<td style=\"padding:6px 12px\">{int(item['quantity'])}</td>"
        f"<td style=\"padding:6px 0 6px 12px; text-align:right\">{escape(format_money(int(item['line_total_minor']), str(order['currency'])))}</td></tr>"
        for item in items
    )
    action_html = ""
    if kind in {"order_confirmation", "payment_failed"} and str(order.get("status")) == "pending" and base_url and signing_secret:
        link = f"{base_url.rstrip('/')}/orders/{create_order_link(order_id, signing_secret)}"
        action = "View your order and complete payment" if kind == "order_confirmation" else "Try payment again"
        action_html = f'<p><a href="{escape(link, quote=True)}">{action}</a></p>'
    currency = str(order["currency"])
    shipping = "Free" if int(order["shipping_minor"]) == 0 else escape(format_money(int(order["shipping_minor"]), currency))
    html = f"""<div style="font-family:Georgia,serif; max-width:560px; margin:0 auto">
  <h2 style="font-weight:normal">Luit &amp; Loom</h2>
  <p>{intro}</p>
  {action_html}
  <table style="border-collapse:collapse; width:100%">
    <thead><tr><th scope="col" style="text-align:left; padding:6px 12px 6px 0">Item</th>
      <th scope="col" style="text-align:left; padding:6px 12px">Qty</th>
      <th scope="col" style="text-align:right; padding:6px 0 6px 12px">Total</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  <p style="text-align:right">Subtotal {escape(format_money(int(order['subtotal_minor']), currency))}<br>
    Shipping {shipping}<br><strong>Total {escape(format_money(int(order['total_minor']), currency))}</strong></p>
  <p>Order reference <strong>{reference}</strong>.</p>
</div>"""
    return OrderEmail(subject, html)


def enqueue_order_email(
    connection,
    kind: str,
    order_id: str,
    to_email: str | None = None,
    at: datetime | None = None,
) -> None:
    if kind not in EMAIL_KINDS:
        raise ValueError(f"unsupported_email_kind:{kind}")
    timestamp = at or _now()
    with connection.cursor() as cursor:
        if not to_email:
            cursor.execute("SELECT email FROM orders WHERE id = %s", (order_id,))
            order = cursor.fetchone()
            to_email = str(order["email"]) if order and order.get("email") else ""
        if not to_email:
            return
        cursor.execute(
            """
            INSERT INTO email_outbox (
              id, kind, order_id, to_email, status, attempts,
              next_attempt_at, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, 'queued', 0, %s, %s, %s)
            ON CONFLICT (order_id, kind) DO NOTHING
            """,
            (str(uuid4()), kind, order_id, to_email, timestamp, timestamp, timestamp),
        )


def _load_order(connection, order_id: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, email, status, currency, subtotal_minor, shipping_minor,
              total_minor, ship_name, ship_city
            FROM orders WHERE id = %s
            """,
            (order_id,),
        )
        order = cursor.fetchone()
        if not order:
            raise ValueError("order_missing")
        cursor.execute(
            """
            SELECT product_title, variant_title, sku, quantity,
              unit_price_minor, line_total_minor
            FROM order_items WHERE order_id = %s ORDER BY created_at ASC, id ASC
            """,
            (order_id,),
        )
        return order, list(cursor.fetchall())


def _send_via_resend(config: MailConfig, to_email: str, message: OrderEmail) -> None:
    request = URLRequest(
        RESEND_ENDPOINT,
        data=dumps(
            {"from": config.from_email, "to": [to_email], "subject": message.subject, "html": message.html}
        ).encode(),
        headers={"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            status = getattr(response, "status", None) or response.getcode()
            if not 200 <= status < 300:
                raise RuntimeError(f"resend_status_{status}")
    except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as error:
        raise RuntimeError("email_delivery_failed") from error


def process_outbox(
    pool: ConnectionPool,
    settings: Settings | None = None,
    limit: int = 25,
) -> dict[str, int]:
    summary = {"sent": 0, "retried": 0, "failed": 0}
    values = settings or Settings.from_env()
    config = mail_config(values)
    if config is None:
        return summary
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, kind, order_id, to_email, attempts
                FROM email_outbox
                WHERE status = 'queued' AND next_attempt_at <= %s
                ORDER BY next_attempt_at ASC, id ASC
                LIMIT %s
                """,
                (_now(), limit),
            )
            due = list(cursor.fetchall())
    for row in due:
        try:
            with pool.connection() as connection:
                order, items = _load_order(connection, str(row["order_id"]))
            message = build_order_email(
                str(row["kind"]),
                order,
                items,
                base_url=config.base_url,
                signing_secret=values.cookie_signing_key,
            )
            _send_via_resend(config, str(row["to_email"]), message)
            with pool.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE email_outbox SET status = 'sent', sent_at = %s, last_error = NULL, updated_at = %s WHERE id = %s",
                        (_now(), _now(), row["id"]),
                    )
            summary["sent"] += 1
        except Exception as error:
            attempts = int(row["attempts"]) + 1
            failed = attempts >= MAX_ATTEMPTS
            next_attempt = _now() + timedelta(minutes=min(BACKOFF_CAP_MINUTES, 2**attempts))
            with pool.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE email_outbox
                        SET status = %s, attempts = %s, next_attempt_at = %s,
                          last_error = %s, updated_at = %s
                        WHERE id = %s
                        """,
                        (
                            "failed" if failed else "queued",
                            attempts,
                            next_attempt,
                            str(error)[:300],
                            _now(),
                            row["id"],
                        ),
                    )
            summary["failed" if failed else "retried"] += 1
    return summary
