from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.admin_auth import AdminSession, session_cookie, verify_session_cookie
from app.admin import allowed_status_transition
from app.inventory import validate_adjustment


SECRET = "test-admin-signing-secret-with-at-least-32-characters"


def test_admin_session_cookie_is_signed_and_tamper_evident() -> None:
    session = AdminSession(
        owner_id="owner",
        session_version=1,
        expires_at=int(datetime.now(timezone.utc).timestamp()) + 3600,
        csrf="csrf-token-with-at-least-thirty-two-characters",
    )

    cookie = session_cookie(session, SECRET)
    assert cookie.startswith("luit_admin=")
    value = cookie.split(";", 1)[0].split("=", 1)[1]
    assert verify_session_cookie(value, SECRET) == session

    tampered = value[:-1] + ("A" if value[-1] != "A" else "B")
    with pytest.raises(HTTPException) as error:
        verify_session_cookie(tampered, SECRET)
    assert error.value.status_code == 401


def test_admin_order_transitions_are_explicit() -> None:
    assert allowed_status_transition("pending", "paid")
    assert allowed_status_transition("pending", "cancelled")
    assert allowed_status_transition("paid", "fulfilled")
    assert allowed_status_transition("paid", "cancelled")
    assert not allowed_status_transition("pending", "fulfilled")
    assert not allowed_status_transition("fulfilled", "cancelled")


def test_inventory_adjustment_input_is_normalised_and_validated() -> None:
    assert validate_adjustment(3, "  stock received\n  ", "123e4567-e89b-42d3-a456-426614174000") == (
        3,
        "stock received",
        "123e4567-e89b-42d3-a456-426614174000",
    )
    with pytest.raises(HTTPException) as error:
        validate_adjustment(0, "stock", "123e4567-e89b-42d3-a456-426614174000")
    assert error.value.status_code == 422


class _StatusCursor:
    def __init__(self, status: str) -> None:
        self.status = status
        self.rowcount = 1
        self.statements: list[tuple[str, tuple[object, ...]]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def execute(self, statement: str, params: tuple[object, ...] = ()) -> None:
        self.statements.append((statement, params))

    def fetchone(self):
        if len(self.statements) == 1:
            return {"id": "123e4567-e89b-12d3-a456-426614174000", "status": self.status}
        return None

    def fetchall(self):
        return []


class _StatusConnection:
    def __init__(self, status: str) -> None:
        self.cursor_instance = _StatusCursor(status)

    def cursor(self):
        return self.cursor_instance

    def transaction(self):
        from contextlib import nullcontext

        return nullcontext()


class _StatusPool:
    def __init__(self, status: str) -> None:
        self.connection_instance = _StatusConnection(status)

    def connection(self):
        from contextlib import nullcontext

        return nullcontext(self.connection_instance)


def test_status_change_queues_shipment_email(monkeypatch) -> None:
    from app.admin import change_order_status

    queued: list[tuple[object, ...]] = []
    monkeypatch.setattr("app.admin.enqueue_order_email", lambda _connection, *args, **kwargs: queued.append(args))

    result = change_order_status(_StatusPool("paid"), "123e4567-e89b-12d3-a456-426614174000", "fulfilled")

    assert result == "fulfilled"
    assert queued and queued[0][0] == "order_shipped"


def test_status_change_queues_cancellation_email_and_releases_reservations(monkeypatch) -> None:
    from app.admin import change_order_status

    queued: list[tuple[object, ...]] = []
    monkeypatch.setattr("app.admin.enqueue_order_email", lambda _connection, *args, **kwargs: queued.append(args))

    result = change_order_status(_StatusPool("pending"), "123e4567-e89b-12d3-a456-426614174000", "cancelled")

    assert result == "cancelled"
    assert queued and queued[0][0] == "order_cancelled"
