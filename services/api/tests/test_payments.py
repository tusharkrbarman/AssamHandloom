from json import dumps

from fastapi.testclient import TestClient

from app.main import app
from app.payments import (
    RazorpayConfig,
    _create_provider_order,
    payment_signature,
    razorpay_config,
    webhook_signature,
)
from app.settings import Settings


SECRET = "test-key-secret-with-at-least-32-characters"
WEBHOOK_SECRET = "test-webhook-secret-with-at-least-32-characters"
ORDER_ID = "123e4567-e89b-12d3-a456-426614174000"
TOKEN = "123e4567-e89b-12d3-a456-426614174001"


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
