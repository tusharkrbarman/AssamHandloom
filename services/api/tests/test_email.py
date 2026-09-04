from contextlib import nullcontext
from datetime import datetime, timedelta, timezone

from app.email import (
    EMAIL_KINDS,
    MailConfig,
    OrderEmail,
    _send_via_resend,
    build_order_email,
    enqueue_order_email,
    mail_config,
    process_outbox,
)
from app.orders import CheckoutRequest, create_order
from app.payments import RazorpayConfig, _process_razorpay_webhook, apply_captured_payment, webhook_signature
from app.settings import Settings


SECRET = "test-signing-secret-with-at-least-32-characters"
ORDER_ID = "123e4567-e89b-12d3-a456-426614174000"


class FakeCursor:
    def __init__(self) -> None:
        self.statements: list[tuple[str, tuple[object, ...]]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, statement: str, params: tuple[object, ...]) -> None:
        self.statements.append((statement, params))


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def transaction(self):
        return nullcontext()


class FakePool:
    def __init__(self) -> None:
        self.connection_instance = FakeConnection()

    def connection(self):
        return nullcontext(self.connection_instance)


class PaymentCursor(FakeCursor):
    def __init__(self, rows: list[dict[str, object]]) -> None:
        super().__init__()
        self.rows = list(rows)
        self.rowcount = 1

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


class PaymentConnection(FakeConnection):
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.cursor_instance = PaymentCursor(rows)


class PaymentPool:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.connection_instance = PaymentConnection(rows)

    def connection(self):
        return nullcontext(self.connection_instance)


class OutboxCursor(FakeCursor):
    def __init__(self) -> None:
        super().__init__()
        self.result_rows: list[dict[str, object]] = []

    def execute(self, statement: str, params: tuple[object, ...]) -> None:
        super().execute(statement, params)
        if "FROM email_outbox" in statement:
            self.result_rows = [
                {
                    "id": "outbox-1",
                    "kind": "order_confirmation",
                    "order_id": ORDER_ID,
                    "to_email": "buyer@example.com",
                    "attempts": 0,
                }
            ]
        elif "FROM orders" in statement:
            self.result_rows = [order_record()]
        elif "FROM order_items" in statement:
            self.result_rows = [
                {
                    "product_title": "Muga Silk",
                    "variant_title": "Gold",
                    "sku": "MUGA-1",
                    "quantity": 1,
                    "unit_price_minor": 125000,
                    "line_total_minor": 125000,
                }
            ]
        else:
            self.result_rows = []

    def fetchone(self):
        return self.result_rows.pop(0) if self.result_rows else None

    def fetchall(self):
        rows = self.result_rows
        self.result_rows = []
        return rows


class OutboxConnection(FakeConnection):
    def __init__(self) -> None:
        self.cursor_instance = OutboxCursor()


class OutboxPool:
    def __init__(self) -> None:
        self.connection_instance = OutboxConnection()

    def connection(self):
        return nullcontext(self.connection_instance)


def order_record(status: str = "pending") -> dict[str, object]:
    return {
        "id": ORDER_ID,
        "email": "buyer@example.com",
        "status": status,
        "currency": "INR",
        "subtotal_minor": 125000,
        "shipping_minor": 0,
        "total_minor": 125000,
        "ship_name": "Asha <Barman>",
        "ship_city": "Guwahati",
    }


def test_mail_config_requires_api_key_and_sender(monkeypatch) -> None:
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("MAIL_FROM", "Luit & Loom <orders@example.com>")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://shop.example")

    assert mail_config() == MailConfig(
        api_key="re_test",
        from_email="Luit & Loom <orders@example.com>",
        base_url="https://shop.example",
    )

    monkeypatch.delenv("MAIL_FROM")
    assert mail_config() is None


def test_confirmation_email_escapes_customer_data_and_contains_order_link() -> None:
    message = build_order_email(
        "order_confirmation",
        order_record(),
        [
            {
                "product_title": "Muga <silk>",
                "variant_title": "Gold",
                "sku": "MUGA-1",
                "quantity": 1,
                "unit_price_minor": 125000,
                "line_total_minor": 125000,
            }
        ],
        base_url="https://shop.example/",
        signing_secret=SECRET,
    )

    assert message.subject.startswith("Your Luit & Loom order ")
    assert "Asha &lt;Barman&gt;" in message.html
    assert "Muga &lt;silk&gt;" in message.html
    assert "https://shop.example/orders/" in message.html
    assert "View your order and complete payment" in message.html


def test_email_kinds_cover_requested_order_events() -> None:
    assert EMAIL_KINDS == {
        "order_confirmation",
        "order_paid",
        "payment_failed",
        "order_shipped",
        "order_cancelled",
        "order_refunded",
    }


def test_enqueue_order_email_is_idempotent() -> None:
    connection = FakeConnection()
    enqueue_order_email(
        connection,
        "order_shipped",
        ORDER_ID,
        "buyer@example.com",
        datetime(2026, 9, 3, tzinfo=timezone.utc),
    )

    statement, params = connection.cursor_instance.statements[0]
    assert "ON CONFLICT (order_id, kind) DO NOTHING" in statement
    assert params[1:4] == ("order_shipped", ORDER_ID, "buyer@example.com")


def test_order_creation_enqueues_confirmation(monkeypatch) -> None:
    pool = FakePool()
    payload = CheckoutRequest.model_validate(
        {
            "items": [{"variantId": "123e4567-e89b-12d3-a456-426614174001", "quantity": 1}],
            "email": "buyer@example.com",
            "name": "Asha Barman",
            "phone": "+919999999999",
            "address1": "1 Silk Road",
            "city": "Guwahati",
            "state": "Assam",
            "postalCode": "781001",
        }
    )
    monkeypatch.setattr(
        "app.orders._variant_rows",
        lambda *_args, **_kwargs: [
            {
                "id": "123e4567-e89b-12d3-a456-426614174001",
                "sku": "MUGA-1",
                "variant_title": "Gold",
                "product_title": "Muga Silk",
                "price_minor": 125000,
                "currency": "INR",
                "quantity": 2,
            }
        ],
    )
    monkeypatch.setattr("app.orders._reserved_rows", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(
        "app.orders._quote_from_rows",
        lambda *_args, **_kwargs: {
            "currency": "INR",
            "lines": [
                {
                    "variantId": "123e4567-e89b-12d3-a456-426614174001",
                    "sku": "MUGA-1",
                    "productTitle": "Muga Silk",
                    "variantTitle": "Gold",
                    "quantity": 1,
                    "unitPriceMinor": 125000,
                    "lineTotalMinor": 125000,
                }
            ],
            "subtotalMinor": 125000,
            "allAvailable": True,
        },
    )
    enqueued: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        "app.orders.enqueue_order_email",
        lambda _connection, *args: enqueued.append(args),
    )

    create_order(pool, payload, SECRET)  # type: ignore[arg-type]

    assert enqueued and enqueued[0][0] == "order_confirmation"
    assert enqueued[0][2] == "buyer@example.com"


def test_captured_payment_enqueues_paid_email(monkeypatch) -> None:
    pool = PaymentPool(
        [
            {
                "id": "payment-1",
                "order_id": ORDER_ID,
                "provider_payment_id": None,
                "status": "created",
            },
            {"id": ORDER_ID, "status": "pending"},
        ]
    )
    monkeypatch.setattr(
        "app.payments._reservation_rows",
        lambda *_args: [
            {
                "id": "reservation-1",
                "variant_id": "123e4567-e89b-12d3-a456-426614174001",
                "quantity": 1,
                "state": "active",
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
                "stock_quantity": 2,
            }
        ],
    )
    enqueued: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        "app.payments.enqueue_order_email",
        lambda _connection, *args, **_kwargs: enqueued.append(args),
    )

    outcome = apply_captured_payment(pool, "payment-1", "pay_rzp_123")  # type: ignore[arg-type]

    assert outcome == "captured"
    assert enqueued and enqueued[0][0] == "order_paid"


def test_failed_payment_webhook_enqueues_failure_email(monkeypatch) -> None:
    pool = PaymentPool([{"order_id": ORDER_ID}])
    raw = (
        '{"event":"payment.failed","payload":{"payment":{"entity":'
        '{"order_id":"order_rzp_123","error_description":"Declined"}}}}'
    ).encode()
    enqueued: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        "app.payments.enqueue_order_email",
        lambda _connection, *args, **_kwargs: enqueued.append(args),
    )

    result = _process_razorpay_webhook(
        pool,  # type: ignore[arg-type]
        raw,
        webhook_signature(raw, "webhook-secret"),
        RazorpayConfig("rzp_test_key", SECRET, "webhook-secret"),
    )

    assert result == {"received": True}
    assert enqueued and enqueued[0][0] == "payment_failed"


def test_process_outbox_sends_and_marks_message_sent(monkeypatch) -> None:
    pool = OutboxPool()
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app.email._send_via_resend",
        lambda _config, to_email, message: sent.append((to_email, message.subject)),
    )
    settings = Settings(
        None,
        SECRET,
        resend_api_key="re_test",
        mail_from="Luit & Loom <orders@example.com>",
        public_base_url="https://shop.example",
    )

    summary = process_outbox(pool, settings)  # type: ignore[arg-type]

    assert summary == {"sent": 1, "retried": 0, "failed": 0}
    assert sent == [("buyer@example.com", f"Your Luit & Loom order {ORDER_ID[:8].upper()}")]
    assert "status = 'sent'" in pool.connection_instance.cursor_instance.statements[-1][0]


def test_process_outbox_requeues_delivery_failures(monkeypatch) -> None:
    pool = OutboxPool()
    monkeypatch.setattr(
        "app.email._send_via_resend",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
    )
    settings = Settings(
        None,
        SECRET,
        resend_api_key="re_test",
        mail_from="Luit & Loom <orders@example.com>",
    )

    summary = process_outbox(pool, settings)  # type: ignore[arg-type]

    assert summary == {"sent": 0, "retried": 1, "failed": 0}
    statement, params = pool.connection_instance.cursor_instance.statements[-1]
    assert "SET status = %s" in statement
    assert params[0] == "queued"
    assert params[1] == 1


def test_resend_sender_posts_the_transactional_message(monkeypatch) -> None:
    seen: dict[str, object] = {}

    class Response:
        status = 202

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def getcode(self) -> int:
            return self.status

    def fake_urlopen(request, timeout):
        seen["request"] = request
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr("app.email.urlopen", fake_urlopen)
    _send_via_resend(
        MailConfig("re_test", "Luit & Loom <orders@example.com>"),
        "buyer@example.com",
        OrderEmail("Subject", "<p>Body</p>"),
    )

    request = seen["request"]
    assert seen["timeout"] == 10
    assert request.full_url == "https://api.resend.com/emails"
    assert request.get_header("Authorization") == "Bearer re_test"
