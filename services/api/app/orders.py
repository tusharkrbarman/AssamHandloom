from datetime import datetime, timedelta, timezone
from re import compile
from uuid import uuid4

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from psycopg_pool import ConnectionPool

from .catalogue import format_money
from .links import create_order_link, verify_order_link


MAX_LINES = 20
MAX_QUANTITY_PER_LINE = 10
RESERVATION_MINUTES = 30
UUID_PATTERN = compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", flags=2)
EMAIL_PATTERN = compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
PHONE_PATTERN = compile(r"^[+0-9][0-9 ()-]+$")

STATUS_LABELS = {
    "pending": "Awaiting payment",
    "paid": "Payment received",
    "fulfilled": "On its way",
    "cancelled": "Cancelled",
    "expired": "Expired",
}


class CartItem(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    variant_id: str = Field(alias="variantId")
    quantity: int = Field(ge=1, le=MAX_QUANTITY_PER_LINE)


class CartQuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[CartItem] = Field(min_length=1, max_length=MAX_LINES)


class CheckoutRequest(CartQuoteRequest):
    email: str
    name: str
    phone: str
    address1: str
    address2: str | None = None
    city: str
    state: str
    postal_code: str = Field(alias="postalCode")
    country: str = "IN"


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean(value: str, label: str, maximum: int, minimum: int = 2) -> str:
    clean = " ".join(value.split())
    if len(clean) < minimum or len(clean) > maximum:
        raise _error(422, "invalid_checkout_field", f"{label} is invalid.")
    return clean


def _normalise_items(items: list[CartItem]) -> list[dict[str, object]]:
    if not items or len(items) > MAX_LINES:
        raise _error(422, "invalid_cart", f"The bag must contain between 1 and {MAX_LINES} items.")
    quantities: dict[str, dict[str, object]] = {}
    for item in items:
        variant_id = item.variant_id.strip()
        if not UUID_PATTERN.fullmatch(variant_id):
            raise _error(422, "invalid_cart", "A bag item reference is invalid.")
        key = variant_id.lower()
        existing = quantities.get(key)
        if existing:
            quantity = int(existing["quantity"]) + item.quantity
            if quantity > MAX_QUANTITY_PER_LINE:
                raise _error(422, "invalid_cart", f"Each item is limited to {MAX_QUANTITY_PER_LINE} per order.")
            existing["quantity"] = quantity
        else:
            quantities[key] = {"variant_id": variant_id, "quantity": item.quantity}
    return list(quantities.values())


def _validate_checkout(payload: CheckoutRequest) -> tuple[list[dict[str, object]], dict[str, str | None]]:
    items = _normalise_items(payload.items)
    email = payload.email.strip()
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        raise _error(422, "invalid_checkout_field", "Email is invalid.")
    phone = _clean(payload.phone, "Phone", 20, 6)
    if not PHONE_PATTERN.fullmatch(phone):
        raise _error(422, "invalid_checkout_field", "Phone is invalid.")
    country = payload.country.strip().upper()
    if country != "IN":
        raise _error(422, "unsupported_country", "We currently ship within India only.")
    fields = {
        "email": email,
        "name": _clean(payload.name, "Full name", 160),
        "phone": phone,
        "address1": _clean(payload.address1, "Address", 200),
        "address2": " ".join(payload.address2.split()) if payload.address2 else None,
        "city": _clean(payload.city, "City", 100),
        "state": _clean(payload.state, "State", 100),
        "postal_code": _clean(payload.postal_code, "Postal code", 20, 3),
        "country": country,
    }
    if fields["address2"] and len(str(fields["address2"])) > 200:
        raise _error(422, "invalid_checkout_field", "The address line is too long.")
    return items, fields


def _money(minor: int, currency: str) -> str:
    return format_money(minor, currency)


def _variant_rows(connection, items: list[dict[str, object]], lock: bool) -> list[dict[str, object]]:
    ids = [str(item["variant_id"]) for item in items]
    lock_clause = " FOR UPDATE OF variant, stock" if lock else ""
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            SELECT variant.id, variant.sku, variant.title AS variant_title,
              product.title AS product_title, variant.price_minor, variant.currency,
              stock.quantity
            FROM variants variant
            JOIN products product ON product.id = variant.product_id
            JOIN inventory_items stock ON stock.variant_id = variant.id
            WHERE variant.id = ANY(%s)
              AND variant.publication_state = 'published'
              AND product.publication_state = 'published'
              AND product.archived_at IS NULL
            ORDER BY variant.id
            {lock_clause}
            """,
            (ids,),
        )
        return list(cursor.fetchall())


def _reserved_rows(connection, ids: list[str], at: datetime) -> dict[str, int]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT variant_id, COALESCE(SUM(quantity), 0) AS reserved
            FROM inventory_reservations
            WHERE variant_id = ANY(%s) AND state = 'active' AND expires_at > %s
            GROUP BY variant_id
            """,
            (ids, at),
        )
        return {str(row["variant_id"]): int(row["reserved"]) for row in cursor.fetchall()}


def _quote_from_rows(
    items: list[dict[str, object]],
    rows: list[dict[str, object]],
    reserved: dict[str, int],
) -> dict[str, object]:
    by_id = {str(row["id"]).lower(): row for row in rows}
    lines: list[dict[str, object]] = []
    currency: str | None = None
    for item in items:
        variant_id = str(item["variant_id"])
        row = by_id.get(variant_id.lower())
        if row is None:
            raise _error(404, "cart_item_unavailable", "An item in your bag is no longer offered.")
        row_currency = str(row["currency"])
        currency = currency or row_currency
        if currency != row_currency:
            raise _error(409, "mixed_currency", "Your bag mixes currencies; please review it.")
        quantity = int(item["quantity"])
        unit_price = int(row["price_minor"])
        line_total = unit_price * quantity
        available_quantity = int(row["quantity"]) - reserved.get(str(row["id"]), 0)
        lines.append(
            {
                "variantId": row["id"],
                "sku": row["sku"],
                "productTitle": row["product_title"],
                "variantTitle": row["variant_title"],
                "quantity": quantity,
                "unitPriceMinor": unit_price,
                "unitPriceFormatted": _money(unit_price, row_currency),
                "lineTotalMinor": line_total,
                "lineTotalFormatted": _money(line_total, row_currency),
                "available": available_quantity >= quantity,
            }
        )
    resolved_currency = currency or "INR"
    subtotal = sum(int(line["lineTotalMinor"]) for line in lines)
    return {
        "currency": resolved_currency,
        "lines": lines,
        "subtotalMinor": subtotal,
        "subtotalFormatted": _money(subtotal, resolved_currency),
        "allAvailable": all(bool(line["available"]) for line in lines),
    }


def quote_cart(pool: ConnectionPool, items: list[CartItem]) -> dict[str, object]:
    normalised = _normalise_items(items)
    at = _now()
    with pool.connection() as connection:
        rows = _variant_rows(connection, normalised, lock=False)
        reserved = _reserved_rows(connection, [str(item["variant_id"]) for item in normalised], at)
    return _quote_from_rows(normalised, rows, reserved)


def create_order(
    pool: ConnectionPool,
    payload: CheckoutRequest,
    signing_secret: str | None,
) -> dict[str, object]:
    if not signing_secret or len(signing_secret) < 32:
        raise _error(503, "invalid_configuration", "Order links are not configured.")
    items, fields = _validate_checkout(payload)
    created_at = _now()
    expires_at = created_at + timedelta(minutes=RESERVATION_MINUTES)
    order_id = str(uuid4())
    token = str(uuid4())
    with pool.connection() as connection:
        with connection.transaction():
            rows = _variant_rows(connection, items, lock=True)
            reserved = _reserved_rows(connection, [str(item["variant_id"]) for item in items], created_at)
            quote = _quote_from_rows(items, rows, reserved)
            if not quote["allAvailable"]:
                raise _error(409, "insufficient_stock", "One or more weaves just sold out. Please review your bag.")
            by_id = {str(row["id"]).lower(): row for row in rows}
            # ponytail: flat shipping placeholder; replace with a shipping policy before live payments
            shipping_minor = 0
            total_minor = int(quote["subtotalMinor"]) + shipping_minor
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO orders (
                      id, token, email, status, currency, subtotal_minor, shipping_minor, total_minor,
                      ship_name, ship_phone, ship_address1, ship_address2, ship_city, ship_state,
                      ship_postal_code, ship_country, created_at, updated_at
                    ) VALUES (%s, %s, %s, 'pending', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        order_id,
                        token,
                        fields["email"],
                        quote["currency"],
                        quote["subtotalMinor"],
                        shipping_minor,
                        total_minor,
                        fields["name"],
                        fields["phone"],
                        fields["address1"],
                        fields["address2"],
                        fields["city"],
                        fields["state"],
                        fields["postal_code"],
                        fields["country"],
                        created_at,
                        created_at,
                    ),
                )
                for line in quote["lines"]:
                    row = by_id[str(line["variantId"]).lower()]
                    cursor.execute(
                        """
                        INSERT INTO order_items (
                          id, order_id, variant_id, product_title, variant_title, sku,
                          unit_price_minor, currency, quantity, line_total_minor, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            str(uuid4()),
                            order_id,
                            line["variantId"],
                            row["product_title"],
                            row["variant_title"],
                            row["sku"],
                            line["unitPriceMinor"],
                            quote["currency"],
                            line["quantity"],
                            line["lineTotalMinor"],
                            created_at,
                        ),
                    )
                    cursor.execute(
                        """
                        INSERT INTO inventory_reservations (
                          id, order_id, variant_id, quantity, state, expires_at, created_at
                        ) VALUES (%s, %s, %s, %s, 'active', %s, %s)
                        """,
                        (
                            str(uuid4()),
                            order_id,
                            line["variantId"],
                            line["quantity"],
                            expires_at,
                            created_at,
                        ),
                    )
    return {
        "orderId": order_id,
        "token": token,
        "orderLink": f"/api/orders/{create_order_link(order_id, signing_secret)}",
        "order": {
            "status": "pending",
            "currency": quote["currency"],
            "subtotalMinor": quote["subtotalMinor"],
            "shippingMinor": shipping_minor,
            "totalMinor": total_minor,
            "lines": quote["lines"],
        },
    }


def _order_response(order: dict[str, object], items: list[dict[str, object]]) -> dict[str, object]:
    currency = str(order["currency"])
    return {
        "id": order["id"],
        "status": order["status"],
        "statusLabel": STATUS_LABELS.get(str(order["status"]), "Processing"),
        "currency": currency,
        "subtotalMinor": order["subtotal_minor"],
        "subtotalFormatted": _money(int(order["subtotal_minor"]), currency),
        "shippingMinor": order["shipping_minor"],
        "totalMinor": order["total_minor"],
        "totalFormatted": _money(int(order["total_minor"]), currency),
        "shipName": order["ship_name"],
        "shipAddress1": order["ship_address1"],
        "shipAddress2": order["ship_address2"],
        "shipCity": order["ship_city"],
        "shipState": order["ship_state"],
        "shipPostalCode": order["ship_postal_code"],
        "shipCountry": order["ship_country"],
        "createdAt": order["created_at"].isoformat() if hasattr(order["created_at"], "isoformat") else order["created_at"],
        "items": items,
    }


def get_order(
    pool: ConnectionPool,
    order_id: str,
    token: str | None,
    expires_at: int | None,
    signature: str | None,
    signing_secret: str | None,
) -> dict[str, object]:
    if not UUID_PATTERN.fullmatch(order_id):
        raise _error(404, "not_found", "That order could not be found.")
    authorized = bool(token)
    if not authorized and signing_secret:
        authorized = verify_order_link(order_id, expires_at, signature, signing_secret)
    if not authorized:
        raise _error(404, "not_found", "That order could not be found.")
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            if token:
                cursor.execute("SELECT * FROM orders WHERE id = %s AND token = %s", (order_id, token))
            else:
                cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
            order = cursor.fetchone()
            if not order:
                raise _error(404, "not_found", "That order could not be found.")
            cursor.execute(
                """
                SELECT product_title, variant_title, sku, quantity, unit_price_minor,
                  currency, line_total_minor
                FROM order_items WHERE order_id = %s ORDER BY created_at ASC, id ASC
                """,
                (order_id,),
            )
            rows = cursor.fetchall()
    items = [
        {
            "productTitle": row["product_title"],
            "variantTitle": row["variant_title"],
            "sku": row["sku"],
            "quantity": row["quantity"],
            "unitPriceMinor": row["unit_price_minor"],
            "unitPriceFormatted": _money(int(row["unit_price_minor"]), str(row["currency"])),
            "lineTotalMinor": row["line_total_minor"],
            "lineTotalFormatted": _money(int(row["line_total_minor"]), str(row["currency"])),
        }
        for row in rows
    ]
    return {"order": _order_response(order, items)}
