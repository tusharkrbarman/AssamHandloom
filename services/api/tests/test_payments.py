from contextlib import nullcontext
from json import dumps
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from app.links import create_order_link
from app.main import app
from app.payments import (
    PaymentSessionRequest,
    PaymentVerifyRequest,
    RazorpayConfig,
    _create_provider_order,
    create_payment_session,
    payment_signature,
    razorpay_config,
    verify_payment,
    webhook_signature,
)
from app.settings import Settings


SECRET = "test-key-secret-with-at-least-32-characters"
WEBHOOK_SECRET = "test-webhook-secret-with-at-least-32-characters"
ORDER_ID = "123e4567-e89b-12d3-a456-426614174000"
TOKEN = "123e4567-e89b-12d3-a456-426614174001"


class FakeCursor:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = list(rows)
        self.statements: list[tuple[str, tuple[object, ...]]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, statement: str, params: tuple[object, ...]) -> None:
        self.statements.append((statement, params))

    def fetchone(self) -> dict[str, object] | None:
        return self.rows.pop(0) if self.rows else None


class FakeConnection:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.cursor_instance = FakeCursor(rows)

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def transaction(self):
        return nullcontext()


class FakePool:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.connection_instance = FakeConnection(rows)

    def connection(self):
        return nullcontext(self.connection_instance)


def signed_access() -> dict[str, object]:
    query = parse_qs(urlsplit(create_order_link(ORDER_ID, SECRET)).query)
    return {"exp": int(query["exp"][0]), "sig": query["sig"][0]}


def payable_order() -> dict[str, object]:
    return {
        "id": ORDER_ID,
        "status": "pending",
        "total_minor": 12500,
        "currency": "INR",
        "reservations_payable": True,
    }


def reusable_payment() -> dict[str, object]:
    return {
        "id": "payment-1",
        "order_id": ORDER_ID,
        "provider_order_id": "order_rzp_123",
        "provider_payment_id": None,
        "amount_minor": 12500,
        "currency": "INR",
        "status": "created",
    }


def test_payment_signatures_are_deterministic_and_tamper_evident() -> None:
    payment = payment_signature("order_rzp_1", "pay_rzp_1", SECRET)
    body = dumps({"event": "payment.captured"}).encode()
    webhook = webhook_signature(body, WEBHOOK_SECRET)

    assert len(payment) == 64
    assert len(webhook) == 64
    assert payment != payment_signature("order_rzp_1", "pay_rzp_2", SECRET)
    assert webhook != webhook_signature(body + b" ", WEBHOOK_SECRET)


def test_razorpay_config_requires_all_credentials() -> None:
    assert razorpay_config(Settings(None, None)) is None
    assert razorpay_config(
        Settings(None, None, "rzp_test_key", SECRET, WEBHOOK_SECRET)
    ) is not None


def test_payment_session_reports_disabled_before_database_access(monkeypatch) -> None:
    for name in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET", "DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)

    response = TestClient(app).post(
        "/api/payments/session",
        headers={"origin": "http://testserver"},
        json={"orderId": ORDER_ID, "token": TOKEN},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "payments_disabled"


def test_provider_order_request_returns_provider_reference(monkeypatch) -> None:
    seen = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def read(self) -> bytes:
            return b'{"id":"order_rzp_123"}'

    def fake_urlopen(request, timeout):
        seen["request"] = request
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr("app.payments.urlopen", fake_urlopen)
    provider_id = _create_provider_order(
        RazorpayConfig("rzp_test_key", SECRET, WEBHOOK_SECRET),
        {"id": ORDER_ID, "total_minor": 12500, "currency": "INR"},
    )

    assert provider_id == "order_rzp_123"
    assert seen["timeout"] == 10
    assert b'"amount": 12500' in seen["request"].data


def test_signed_link_authorizes_a_payment_session_without_the_order_token() -> None:
    pool = FakePool([payable_order(), reusable_payment()])
    payload = PaymentSessionRequest.model_validate({"orderId": ORDER_ID, **signed_access()})

    result = create_payment_session(
        pool,  # type: ignore[arg-type]
        payload,
        RazorpayConfig("rzp_test_key", SECRET, WEBHOOK_SECRET),
        SECRET,
    )

    assert result["razorpayOrderId"] == "order_rzp_123"
    assert pool.connection_instance.cursor_instance.statements[0][1][-2:] == (None, None)


def test_signed_link_authorizes_payment_verification_without_the_order_token(monkeypatch) -> None:
    pool = FakePool([reusable_payment()])
    monkeypatch.setattr("app.payments.apply_captured_payment", lambda *_args: "captured")
    payload = PaymentVerifyRequest.model_validate(
        {
            "orderId": ORDER_ID,
            **signed_access(),
            "razorpayOrderId": "order_rzp_123",
            "razorpayPaymentId": "pay_rzp_123",
            "signature": payment_signature("order_rzp_123", "pay_rzp_123", SECRET),
        }
    )

    result = verify_payment(
        pool,  # type: ignore[arg-type]
        payload,
        RazorpayConfig("rzp_test_key", SECRET, WEBHOOK_SECRET),
        SECRET,
    )

    assert result == {"status": "paid"}
    assert pool.connection_instance.cursor_instance.statements[0][1][-2:] == (None, None)


def test_payment_session_keeps_token_clients_compatible() -> None:
    pool = FakePool([payable_order(), reusable_payment()])
    payload = PaymentSessionRequest.model_validate({"orderId": ORDER_ID, "token": TOKEN})

    create_payment_session(
        pool,  # type: ignore[arg-type]
        payload,
        RazorpayConfig("rzp_test_key", SECRET, WEBHOOK_SECRET),
        None,
    )

    assert pool.connection_instance.cursor_instance.statements[0][1][-2:] == (TOKEN, TOKEN)


def test_payment_routes_pass_the_cookie_signing_secret(monkeypatch) -> None:
    received = {}
    monkeypatch.setenv("COOKIE_SIGNING_KEY", SECRET)
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_key")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", SECRET)
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setattr("app.main.request_pool", lambda _request: object())
    monkeypatch.setattr(
        "app.main.create_payment_session",
        lambda _pool, payload, _config, signing_secret: (
            received.update(session=(payload, signing_secret))
            or {"keyId": "rzp_test_key", "razorpayOrderId": "order_rzp_123", "amountMinor": 12500, "currency": "INR"}
        ),
    )
    monkeypatch.setattr(
        "app.main.verify_payment",
        lambda _pool, payload, _config, signing_secret: (
            received.update(verify=(payload, signing_secret)) or {"status": "paid"}
        ),
    )
    client = TestClient(app)
    access = signed_access()

    session = client.post(
        "/api/payments/session",
        headers={"origin": "http://testserver"},
        json={"orderId": ORDER_ID, **access},
    )
    verification = client.post(
        "/api/payments/verify",
        headers={"origin": "http://testserver"},
        json={
            "orderId": ORDER_ID,
            **access,
            "razorpayOrderId": "order_rzp_123",
            "razorpayPaymentId": "pay_rzp_123",
            "signature": "a" * 64,
        },
    )

    assert session.status_code == 200
    assert verification.status_code == 200
    assert received["session"][0].token is None
    assert received["verify"][0].token is None
    assert received["session"][1] == SECRET
    assert received["verify"][1] == SECRET
