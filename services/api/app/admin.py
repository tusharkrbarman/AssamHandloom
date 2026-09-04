from datetime import datetime, timezone
from html import escape
from re import compile
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from .admin_auth import (
    AuthenticatedOwner,
    clear_session_cookie,
    create_owner,
    form_value,
    lockout_key,
    new_session,
    normalised_email,
    owner_record,
    password_matches,
    record_failure,
    require_csrf,
    require_owner,
    reset_owner_password,
    secret_matches,
    session_cookie,
    valid_password,
    check_lockout,
)
from .dependencies import request_pool, require_same_origin
from .email import enqueue_order_email
from .inventory import adjust_inventory, list_inventory
from .catalogue import format_money
from .payments import _settle_reserved_order_locked
from .refunds import refund_order_payment
from .settings import Settings


router = APIRouter()
UUID_PATTERN = compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", flags=2)
STATUS_FILTERS = ("all", "pending", "paid", "fulfilled", "cancelled", "expired")
ADMIN_STATUS_LABELS = {
    "pending": "Awaiting payment",
    "paid": "Paid",
    "fulfilled": "Shipped",
    "cancelled": "Cancelled",
    "expired": "Expired",
}
STATUS_LABELS = ADMIN_STATUS_LABELS
NEXT_ACTIONS = {
    "pending": (("paid", "Mark as paid"), ("cancelled", "Cancel order")),
    "paid": (("fulfilled", "Mark as shipped"), ("cancelled", "Cancel order")),
    "fulfilled": (),
    "cancelled": (),
    "expired": (),
}


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def allowed_status_transition(current: str, next_status: str) -> bool:
    return any(target == next_status for target, _label in NEXT_ACTIONS.get(current, ()))


def _admin_page(title: str, body: str, owner: AuthenticatedOwner | None = None, status_code: int = 200) -> HTMLResponse:
    nav = ""
    if owner:
        csrf = escape(owner.session.csrf, quote=True)
        nav = f"""
        <nav aria-label=\"Admin\"><a href=\"/admin/orders\">Orders</a> ·
        <a href=\"/admin/inventory\">Inventory</a> · <a href=\"/\">Storefront</a>
        <form method=\"post\" action=\"/admin/logout\" style=\"display:inline\">
          <input type=\"hidden\" name=\"csrf\" value=\"{csrf}\"><button type=\"submit\">Sign out</button>
        </form></nav>"""
    html = f"""<!doctype html>
<html lang=\"en-IN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>{escape(title)} · Luit &amp; Loom</title><link rel=\"stylesheet\" href=\"/css/site.css\"></head>
<body><a class=\"skip-link\" href=\"#main-content\">Skip to content</a>
<main id=\"main-content\" class=\"container editorial-page\" tabindex=\"-1\">
<p class=\"eyebrow\">Luit &amp; Loom · Store admin</p>{nav}<h1>{escape(title)}</h1>{body}
</main></body></html>"""
    response = HTMLResponse(html, status_code=status_code)
    response.headers["cache-control"] = "no-store"
    return response


def _auth_page(title: str, body: str, status_code: int = 200) -> HTMLResponse:
    return _admin_page(title, body, status_code=status_code)


def _field(form, name: str) -> str:
    return form_value(form, name)


def _parse_form_int(value: str) -> int:
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        raise _error(422, "invalid_number", "Enter a valid number.") from None


def _order_id(value: str) -> str:
    clean = value.strip().lower()
    if not UUID_PATTERN.fullmatch(clean):
        raise _error(404, "not_found", "That order could not be found.")
    return clean


def _owner_or_redirect(request: Request, pool, settings: Settings) -> AuthenticatedOwner | RedirectResponse:
    try:
        return require_owner(request, pool, settings.cookie_signing_key)
    except HTTPException as error:
        if error.status_code == 401:
            return RedirectResponse("/admin/login", status_code=303)
        raise


def _pool_or_redirect(request: Request):
    try:
        return request_pool(request)
    except HTTPException as error:
        if error.status_code == 503 and not request.headers.get("cookie"):
            return RedirectResponse("/admin/login", status_code=303)
        raise


@router.get("/admin/setup")
def admin_setup_page() -> HTMLResponse:
    return _auth_page(
        "Owner setup",
        """<p>Create the single store-owner account. This page closes after setup.</p>
        <form method=\"post\" action=\"/admin/setup\">
          <label>Setup token <input name=\"token\" type=\"password\" required autocomplete=\"off\"></label>
          <label>Email <input name=\"email\" type=\"email\" required autocomplete=\"username\"></label>
          <label>Password <input name=\"password\" type=\"password\" minlength=\"12\" maxlength=\"128\" required autocomplete=\"new-password\"></label>
          <button type=\"submit\">Create owner</button>
        </form>""",
    )


@router.post("/admin/setup")
async def admin_setup(request: Request) -> RedirectResponse:
    require_same_origin(request)
    settings = Settings.from_env()
    if not settings.admin_setup_token:
        raise _error(503, "invalid_configuration", "Owner setup is not configured.")
    form = await request.form()
    token = _field(form, "token")
    if len(token) < 32 or not secret_matches(token, settings.admin_setup_token):
        raise _error(403, "invalid_credentials", "The supplied credentials are invalid.")
    email = normalised_email(_field(form, "email"))
    password = valid_password(_field(form, "password"))
    pool = request_pool(request)
    with pool.connection() as connection:
        with connection.transaction():
            if owner_record(connection):
                raise _error(409, "setup_unavailable", "Owner setup is already complete.")
            create_owner(connection, email, password)
    return RedirectResponse("/admin/login?setup=complete", status_code=303)


@router.get("/admin/login")
def admin_login_page(request: Request) -> HTMLResponse:
    message = ""
    if request.query_params.get("setup") == "complete":
        message = "<p role=\"status\">Owner created. Sign in to continue.</p>"
    elif request.query_params.get("recovered") == "complete":
        message = "<p role=\"status\">Access restored. Sign in with your new password.</p>"
    return _auth_page(
        "Owner sign in",
        f"""{message}<form method=\"post\" action=\"/admin/login\">
          <label>Email <input name=\"email\" type=\"email\" required autocomplete=\"username\"></label>
          <label>Password <input name=\"password\" type=\"password\" required autocomplete=\"current-password\"></label>
          <button type=\"submit\">Sign in</button>
        </form><p><a href=\"/admin/recover\">Recover owner access</a></p>""",
    )


@router.post("/admin/login")
async def admin_login(request: Request) -> RedirectResponse:
    require_same_origin(request)
    settings = Settings.from_env()
    form = await request.form()
    email = normalised_email(_field(form, "email"))
    password = valid_password(_field(form, "password"))
    pool = request_pool(request)
    key = lockout_key(request, email)
    with pool.connection() as connection:
        with connection.transaction():
            if check_lockout(connection, key):
                raise _error(429, "login_locked", "Sign in is temporarily unavailable.")
            owner = owner_record(connection)
            matched = password_matches(password, owner) if owner and owner.email == email else password_matches(password, None)
            if not owner or owner.email != email or not matched:
                record_failure(connection, key)
                raise _error(401, "invalid_credentials", "Email or password is incorrect.")
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM login_lockouts WHERE key_hash = %s", (key,))
            session = new_session(owner.session_version)
    response = RedirectResponse("/admin/orders", status_code=303)
    response.headers["set-cookie"] = session_cookie(session, settings.cookie_signing_key or "")
    return response


@router.get("/admin/recover")
def admin_recover_page() -> HTMLResponse:
    return _auth_page(
        "Recover owner access",
        """<p>Use the separate recovery token stored with the deployment.</p>
        <form method=\"post\" action=\"/admin/recover\">
          <label>Recovery token <input name=\"token\" type=\"password\" required autocomplete=\"off\"></label>
          <label>Owner email <input name=\"email\" type=\"email\" required autocomplete=\"username\"></label>
          <label>New password <input name=\"password\" type=\"password\" minlength=\"12\" maxlength=\"128\" required autocomplete=\"new-password\"></label>
          <button type=\"submit\">Reset password</button>
        </form>""",
    )


@router.post("/admin/recover")
async def admin_recover(request: Request) -> RedirectResponse:
    require_same_origin(request)
    settings = Settings.from_env()
    if not settings.admin_recovery_token:
        raise _error(503, "invalid_configuration", "Owner recovery is not configured.")
    form = await request.form()
    token = _field(form, "token")
    email = normalised_email(_field(form, "email"))
    password = valid_password(_field(form, "password"))
    if len(token) < 32 or not secret_matches(token, settings.admin_recovery_token):
        raise _error(403, "invalid_credentials", "The supplied credentials are invalid.")
    pool = request_pool(request)
    with pool.connection() as connection:
        with connection.transaction():
            if not reset_owner_password(connection, email, password):
                raise _error(403, "invalid_credentials", "The supplied credentials are invalid.")
    return RedirectResponse("/admin/login?recovered=complete", status_code=303)


@router.post("/admin/logout")
async def admin_logout(request: Request) -> RedirectResponse:
    settings = Settings.from_env()
    pool = request_pool(request)
    authenticated = require_owner(request, pool, settings.cookie_signing_key)
    form = await request.form()
    require_csrf(request, authenticated.session, form)
    response = RedirectResponse("/admin/login", status_code=303)
    response.headers["set-cookie"] = clear_session_cookie()
    return response


def _order_list(pool, status_filter: str) -> list[dict[str, object]]:
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            if status_filter == "all":
                cursor.execute(
                    """
                    SELECT o.id, o.email, o.ship_name, o.status, o.currency,
                      o.total_minor, o.created_at,
                      COALESCE((SELECT SUM(r.amount_minor) FROM order_refunds r
                        WHERE r.order_id = o.id AND r.status = 'processed'), 0) AS refunded_minor
                    FROM orders o ORDER BY o.created_at DESC LIMIT 200
                    """,
                    (),
                )
            else:
                cursor.execute(
                    """
                    SELECT o.id, o.email, o.ship_name, o.status, o.currency,
                      o.total_minor, o.created_at,
                      COALESCE((SELECT SUM(r.amount_minor) FROM order_refunds r
                        WHERE r.order_id = o.id AND r.status = 'processed'), 0) AS refunded_minor
                    FROM orders o WHERE o.status = %s
                    ORDER BY o.created_at DESC LIMIT 200
                    """,
                    (status_filter,),
                )
            return list(cursor.fetchall())


def _short_time(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return str(value)[:16].replace("T", " ")


def _short_reference(value: object) -> str:
    return str(value)[:8].upper()


def _money(minor: object, currency: object) -> str:
    return format_money(int(minor), str(currency))


def _orders_page(pool, owner: AuthenticatedOwner, status_filter: str) -> HTMLResponse:
    rows = _order_list(pool, status_filter)
    filters = " · ".join(
        f"<a href=\"/admin/orders{'' if value == 'all' else '?status=' + value}\"{' aria-current=\"page\"' if value == status_filter else ''}>{escape('All' if value == 'all' else ADMIN_STATUS_LABELS.get(value, value))}</a>"
        for value in STATUS_FILTERS
    )
    table_rows = "".join(
        f"<tr><td><a href=\"/admin/orders/{escape(str(row['id']), quote=True)}\">{escape(_short_reference(row['id']))}</a></td>"
        f"<td>{escape(str(row['ship_name']))}</td><td>{escape(str(row['email']))}</td>"
        f"<td>{'Refunded' if int(row['refunded_minor'] or 0) >= int(row['total_minor']) and int(row['total_minor']) > 0 else escape(ADMIN_STATUS_LABELS.get(str(row['status']), str(row['status'])))}</td>"
        f"<td>{escape(_money(row['total_minor'], row['currency']))}</td><td>{escape(_short_time(row['created_at']))}</td></tr>"
        for row in rows
    )
    body = f"<p>{filters}</p><table><thead><tr><th>Reference</th><th>Customer</th><th>Email</th><th>Status</th><th>Total</th><th>Placed</th></tr></thead><tbody>{table_rows or '<tr><td colspan=\"6\">No orders yet.</td></tr>'}</tbody></table>"
    return _admin_page("Orders", body, owner)


def _order_detail(pool, order_id: str) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    with pool.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
            order = cursor.fetchone()
            if not order:
                raise _error(404, "not_found", "That order could not be found.")
            cursor.execute("SELECT product_title, variant_title, sku, quantity, unit_price_minor, currency, line_total_minor FROM order_items WHERE order_id = %s ORDER BY created_at ASC, id ASC", (order_id,))
            items = list(cursor.fetchall())
            cursor.execute("SELECT id, provider_order_id, provider_payment_id, amount_minor, currency, status, failure_reason FROM order_payments WHERE order_id = %s ORDER BY created_at DESC", (order_id,))
            payments = list(cursor.fetchall())
            cursor.execute("SELECT id, payment_id, provider_refund_id, amount_minor, currency, status, created_at FROM order_refunds WHERE order_id = %s ORDER BY created_at DESC", (order_id,))
            refunds = list(cursor.fetchall())
    return order, items, payments, refunds


def _order_detail_page(pool, owner: AuthenticatedOwner, order_id: str) -> HTMLResponse:
    order, items, payments, refunds = _order_detail(pool, order_id)
    actions = " ".join(
        f"<form method=\"post\" action=\"/admin/orders/{escape(order_id, quote=True)}/status\" style=\"display:inline\"><input type=\"hidden\" name=\"csrf\" value=\"{escape(owner.session.csrf, quote=True)}\"><input type=\"hidden\" name=\"status\" value=\"{target}\"><button type=\"submit\">{label}</button></form>"
        for target, label in NEXT_ACTIONS.get(str(order["status"]), ())
    )
    item_rows = "".join(
        f"<tr><td>{escape(str(item['product_title']))} · {escape(str(item['variant_title']))}<br><small>{escape(str(item['sku']))}</small></td><td>{int(item['quantity'])}</td><td>{escape(_money(item['unit_price_minor'], item['currency']))}</td><td>{escape(_money(item['line_total_minor'], item['currency']))}</td></tr>"
        for item in items
    )
    payment_rows = "".join(
        f"<tr><td>{escape(str(payment['provider_order_id']))}</td><td>{escape(str(payment['provider_payment_id'] or '—'))}</td><td>{escape(str(payment['status']))}</td><td>{escape(_money(payment['amount_minor'], payment['currency']))}</td><td>{escape(str(payment['failure_reason'] or ''))}</td></tr>"
        for payment in payments
    )
    refund_rows = "".join(
        f"<tr><td>{escape(str(refund['provider_refund_id']))}</td><td>{escape(str(refund['status']))}</td><td>{escape(_money(refund['amount_minor'], refund['currency']))}</td><td>{escape(_short_time(refund['created_at']))}</td></tr>"
        for refund in refunds
    )
    captured = next((payment for payment in payments if payment["status"] == "captured" and payment["provider_payment_id"]), None)
    refunded_total = sum(int(refund["amount_minor"]) for refund in refunds if refund["status"] != "failed")
    remaining = int(captured["amount_minor"]) - refunded_total if captured else 0
    payment_review = (
        "<p role=\"alert\"><strong>Payment requires review.</strong> Money was captured after this order closed; refund it unless fulfilment is confirmed manually.</p>"
        if captured and str(order["status"]) not in {"paid", "fulfilled"}
        else ""
    )
    refund_form = ""
    if captured and remaining > 0:
        refund_form = f"<form method=\"post\" action=\"/admin/orders/{escape(order_id, quote=True)}/refund\"><input type=\"hidden\" name=\"csrf\" value=\"{escape(owner.session.csrf, quote=True)}\"><label>Amount in paise <input name=\"amount_minor\" type=\"number\" min=\"1\" max=\"{remaining}\" placeholder=\"Full refund\"></label><button type=\"submit\">Issue refund</button></form>"
    body = f"""<p>Status <strong>{escape(ADMIN_STATUS_LABELS.get(str(order['status']), str(order['status'])))}</strong> · Placed {escape(_short_time(order['created_at']))}</p>
    <h2>Fulfilment</h2>{actions or '<p>This order is closed; no further changes are available.</p>'}
    <h2>Items</h2><table><thead><tr><th>Item</th><th>Qty</th><th>Each</th><th>Total</th></tr></thead><tbody>{item_rows or '<tr><td colspan=\"4\">No items recorded.</td></tr>'}</tbody></table>
    <p>Subtotal {escape(_money(order['subtotal_minor'], order['currency']))}<br>Shipping {escape(_money(order['shipping_minor'], order['currency']))}<br><strong>Total {escape(_money(order['total_minor'], order['currency']))}</strong></p>
    <h2>Customer</h2><p><a href=\"mailto:{escape(str(order['email']), quote=True)}\">{escape(str(order['email']))}</a><br>{escape(str(order['ship_phone']))}</p>
    <h2>Shipping address</h2><p>{escape(str(order['ship_name']))}<br>{escape(str(order['ship_address1']))}{('<br>' + escape(str(order['ship_address2']))) if order['ship_address2'] else ''}<br>{escape(str(order['ship_city']))}, {escape(str(order['ship_state']))} {escape(str(order['ship_postal_code']))}<br>{escape(str(order['ship_country']))}</p>
    <h2>Payments</h2><table><thead><tr><th>Provider order</th><th>Payment</th><th>Status</th><th>Amount</th><th>Note</th></tr></thead><tbody>{payment_rows or '<tr><td colspan=\"5\">No online payments recorded.</td></tr>'}</tbody></table>
    <h2>Refunds</h2>{payment_review}{'<table><thead><tr><th>Refund</th><th>Status</th><th>Amount</th><th>Time</th></tr></thead><tbody>' + refund_rows + '</tbody></table>' if refund_rows else '<p>No refunds issued yet.</p>'}{refund_form}<p><a href=\"/admin/orders\">Back to all orders</a></p>"""
    return _admin_page(f"Order {_short_reference(order_id)}", body, owner)


def change_order_status(pool, order_id: str, next_status: str, actor: str = "owner") -> str:
    order_id = order_id.strip().lower() if isinstance(order_id, str) else ""
    if not UUID_PATTERN.fullmatch(order_id):
        raise _error(422, "invalid_order_status", "That status change is not offered.")
    if next_status not in {target for actions in NEXT_ACTIONS.values() for target, _label in actions}:
        raise _error(422, "invalid_order_status", "That status change is not offered.")
    with pool.connection() as connection:
        with connection.transaction():
            with connection.cursor() as cursor:
                cursor.execute("SELECT id, status FROM orders WHERE id = %s FOR UPDATE", (order_id,))
                order = cursor.fetchone()
            if not order:
                raise _error(404, "not_found", "That order could not be found.")
            current = str(order["status"])
            if not allowed_status_transition(current, next_status):
                raise _error(409, "invalid_status_transition", f"An order marked {ADMIN_STATUS_LABELS.get(current, current)} cannot move there.")
            if next_status == "paid":
                outcome = _settle_reserved_order_locked(connection, order, actor)
                if outcome == "expired":
                    raise _error(409, "reservation_expired", "The reservation is no longer available, so this order cannot be marked paid.")
                return outcome
            now = datetime.now(timezone.utc)
            with connection.cursor() as cursor:
                cursor.execute("UPDATE orders SET status = %s, updated_at = %s WHERE id = %s AND status = %s", (next_status, now, order_id, current))
                if cursor.rowcount != 1:
                    raise _error(409, "order_conflict", "The order changed before this update completed.")
                if next_status == "cancelled":
                    cursor.execute("UPDATE inventory_reservations SET state = 'released' WHERE order_id = %s AND state = 'active'", (order_id,))
                    enqueue_order_email(connection, "order_cancelled", order_id, at=now)
                elif next_status == "fulfilled":
                    enqueue_order_email(connection, "order_shipped", order_id, at=now)
            return next_status


@router.get("/admin")
def admin_home() -> RedirectResponse:
    return RedirectResponse("/admin/orders", status_code=303)


@router.get("/admin/orders")
def admin_orders(request: Request) -> Response:
    settings = Settings.from_env()
    pool = _pool_or_redirect(request)
    if isinstance(pool, RedirectResponse):
        return pool
    owner = _owner_or_redirect(request, pool, settings)
    if isinstance(owner, RedirectResponse):
        return owner
    requested = request.query_params.get("status", "all")
    return _orders_page(pool, owner, requested if requested in STATUS_FILTERS else "all")


@router.get("/admin/orders/{order_id}")
def admin_order_detail(order_id: str, request: Request) -> Response:
    settings = Settings.from_env()
    pool = _pool_or_redirect(request)
    if isinstance(pool, RedirectResponse):
        return pool
    owner = _owner_or_redirect(request, pool, settings)
    if isinstance(owner, RedirectResponse):
        return owner
    return _order_detail_page(pool, owner, _order_id(order_id))


@router.post("/admin/orders/{order_id}/status")
async def admin_order_status(order_id: str, request: Request) -> RedirectResponse:
    settings = Settings.from_env()
    pool = _pool_or_redirect(request)
    if isinstance(pool, RedirectResponse):
        return pool
    owner = _owner_or_redirect(request, pool, settings)
    if isinstance(owner, RedirectResponse):
        return owner
    form = await request.form()
    require_csrf(request, owner.session, form)
    change_order_status(pool, order_id, _field(form, "status"), str(owner.owner["id"]))
    return RedirectResponse(f"/admin/orders/{_order_id(order_id)}", status_code=303)


@router.post("/admin/orders/{order_id}/refund")
async def admin_order_refund(order_id: str, request: Request) -> RedirectResponse:
    settings = Settings.from_env()
    pool = _pool_or_redirect(request)
    if isinstance(pool, RedirectResponse):
        return pool
    owner = _owner_or_redirect(request, pool, settings)
    if isinstance(owner, RedirectResponse):
        return owner
    form = await request.form()
    require_csrf(request, owner.session, form)
    raw = _field(form, "amount_minor").strip()
    amount = None if not raw else _parse_form_int(raw)
    refund_order_payment(pool, _order_id(order_id), amount, settings)
    return RedirectResponse(f"/admin/orders/{_order_id(order_id)}", status_code=303)


@router.get("/admin/inventory")
def admin_inventory(request: Request) -> Response:
    settings = Settings.from_env()
    pool = _pool_or_redirect(request)
    if isinstance(pool, RedirectResponse):
        return pool
    owner = _owner_or_redirect(request, pool, settings)
    if isinstance(owner, RedirectResponse):
        return owner
    rows = list_inventory(pool)
    body_rows = "".join(
                    f"<tr><td>{escape(str(row['sku']))}</td><td>{escape(str(row['productTitle']))}</td><td>{int(row['quantity'])}</td><td><form method=\"post\" action=\"/admin/inventory/{escape(str(row['variantId']), quote=True)}/adjust\"><input type=\"hidden\" name=\"csrf\" value=\"{escape(owner.session.csrf, quote=True)}\"><input type=\"hidden\" name=\"idempotency_key\" value=\"{uuid4()}\"><label>Change <input name=\"delta\" type=\"number\" required></label><label>Reason <input name=\"reason\" minlength=\"3\" maxlength=\"200\" required></label><button type=\"submit\">Adjust</button></form></td></tr>"
        for row in rows
    )
    body = f"<table><thead><tr><th>SKU</th><th>Product</th><th>Quantity</th><th>Adjust</th></tr></thead><tbody>{body_rows or '<tr><td colspan=\"4\">No variants yet.</td></tr>'}</tbody></table>"
    return _admin_page("Inventory", body, owner)


@router.post("/admin/inventory/{variant_id}/adjust")
async def admin_inventory_adjust(variant_id: str, request: Request) -> RedirectResponse:
    settings = Settings.from_env()
    pool = _pool_or_redirect(request)
    if isinstance(pool, RedirectResponse):
        return pool
    owner = _owner_or_redirect(request, pool, settings)
    if isinstance(owner, RedirectResponse):
        return owner
    form = await request.form()
    require_csrf(request, owner.session, form)
    adjust_inventory(pool, variant_id, _parse_form_int(_field(form, "delta")), _field(form, "reason"), _field(form, "idempotency_key"), str(owner.owner["id"]))
    return RedirectResponse("/admin/inventory", status_code=303)
