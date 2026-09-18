from time import time
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from app.links import create_order_link, verify_order_link
from app.main import app


SECRET = "test-signing-secret-with-at-least-32-characters"
ORDER_ID = "123e4567-e89b-12d3-a456-426614174000"


def test_signed_order_link_rejects_tampering_and_expiry() -> None:
    link = create_order_link(ORDER_ID, SECRET)
    query = parse_qs(urlsplit(f"https://example.test/orders/{link}").query)
    expires_at = int(query["exp"][0])
    signature = query["sig"][0]

    assert verify_order_link(ORDER_ID, expires_at, signature, SECRET)
    changed = ("0" if signature[0] != "0" else "1") + signature[1:]
    assert not verify_order_link(ORDER_ID, expires_at, changed, SECRET)
    assert not verify_order_link(ORDER_ID, int(time()) - 1, signature, SECRET)


def test_cart_quote_rejects_missing_or_cross_origin_before_database_access() -> None:
    response = TestClient(app).post(
        "/api/cart/quote",
        json={"items": [{"variantId": ORDER_ID, "quantity": 1}]},
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "invalid_origin"

    response = TestClient(app).post(
        "/api/cart/quote",
        headers={"origin": "https://attacker.example"},
        json={"items": [{"variantId": ORDER_ID, "quantity": 1}]},
    )
    assert response.status_code == 403
