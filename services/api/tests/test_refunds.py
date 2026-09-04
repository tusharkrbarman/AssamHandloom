from contextlib import nullcontext

from app.payments import RazorpayConfig
from app.refunds import refund_order_payment
from app.settings import Settings


ORDER_ID = "123e4567-e89b-12d3-a456-426614174000"


class RefundCursor:
    def __init__(self) -> None:
        self.rowcount = 1
        self.statements: list[tuple[str, tuple[object, ...]]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, statement: str, params: tuple[object, ...] = ()) -> None:
        self.statements.append((statement, params))

    def fetchone(self):
        statement = self.statements[-1][0]
        if "FROM order_payments" in statement:
            return {"id": "payment-1", "provider_payment_id": "pay_123", "amount_minor": 12500, "currency": "INR"}
        if "FROM order_refunds" in statement:
            return {"total": 0, "attempts": 0}
        return None


class RefundConnection:
    def __init__(self) -> None:
        self.cursor_instance = RefundCursor()

    def cursor(self):
        return self.cursor_instance

    def transaction(self):
        return nullcontext()


class RefundPool:
    def __init__(self) -> None:
        self.connection_instance = RefundConnection()

    def connection(self):
        return nullcontext(self.connection_instance)


def test_refund_queues_refund_email(monkeypatch) -> None:
    monkeypatch.setattr("app.refunds.razorpay_config", lambda _settings: RazorpayConfig("key", "secret", "webhook"))
    monkeypatch.setattr("app.refunds._post_refund", lambda *_args: ("rfnd_123", "processed"))
    queued: list[tuple[object, ...]] = []
    monkeypatch.setattr("app.refunds.enqueue_order_email", lambda _connection, *args, **kwargs: queued.append(args))

    result = refund_order_payment(RefundPool(), ORDER_ID, settings=Settings(None, None))  # type: ignore[arg-type]

    assert result["status"] == "processed"
    assert queued and queued[0][0] == "order_refunded"
