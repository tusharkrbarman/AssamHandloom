from fastapi.testclient import TestClient

from app.main import app


PUBLISHED_PRODUCT = {
    "id": "product-golden-muga",
    "slug": "golden-muga",
    "title": "Golden Muga",
    "silkType": "Muga",
    "colour": "Gold",
    "priceMinor": 250000,
    "currency": "INR",
    "available": True,
    "mediaId": None,
    "altText": None,
    "publicationState": "published",
}


def _page(*items: dict[str, object]) -> dict[str, object]:
    return {"items": list(items), "page": 1, "pageSize": 12, "total": len(items)}


def test_home_renders_hero_and_published_catalogue_items(monkeypatch) -> None:
    monkeypatch.setattr("app.web.request_pool", lambda _request: object())
    monkeypatch.setattr("app.web.list_products", lambda _pool, _query: _page(PUBLISHED_PRODUCT))

    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "Woven by Assam." in response.text
    assert "Golden Muga" in response.text


def test_shop_excludes_draft_items_from_the_catalogue(monkeypatch) -> None:
    draft = {
        **PUBLISHED_PRODUCT,
        "title": "Draft Muga",
        "slug": "draft-muga",
        "publicationState": "draft",
    }
    products = [PUBLISHED_PRODUCT, draft]

    def list_published_products(_pool, _query):
        return _page(*(product for product in products if product["publicationState"] == "published"))

    monkeypatch.setattr("app.web.request_pool", lambda _request: object())
    monkeypatch.setattr("app.web.list_products", list_published_products)

    response = TestClient(app).get("/shop")

    assert response.status_code == 200
    assert "Golden Muga" in response.text
    assert draft["title"] not in response.text


def test_shop_pagination_keeps_active_filters(monkeypatch) -> None:
    monkeypatch.setattr("app.web.request_pool", lambda _request: object())
    monkeypatch.setattr(
        "app.web.list_products",
        lambda _pool, _query: {**_page(PUBLISHED_PRODUCT), "total": 24},
    )

    response = TestClient(app).get("/shop?search=Muga&silk_type=Muga&sort=newest")

    assert response.status_code == 200
    assert 'href="/shop?search=Muga&amp;silk_type=Muga&amp;sort=newest&amp;page=2"' in response.text


def test_unknown_api_path_keeps_a_json_not_found_response() -> None:
    response = TestClient(app).get("/api/not-real")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {"detail": "Not Found"}


def test_missing_product_renders_the_branded_not_found_page(monkeypatch) -> None:
    monkeypatch.setattr("app.web.request_pool", lambda _request: object())
    monkeypatch.setattr("app.web.get_product", lambda _pool, _slug: None)

    response = TestClient(app).get("/products/missing")

    assert response.status_code == 404
    assert "We couldn’t find that weave" in response.text


def test_editorial_page_preserves_our_story_copy() -> None:
    response = TestClient(app).get("/our-story")

    assert response.status_code == 200
    assert "Luit &amp; Loom presents Assamese handloom with care." in response.text


def test_public_shell_assets_are_served() -> None:
    client = TestClient(app)

    assert client.get("/css/site.css").status_code == 200
    assert client.get("/js/bag.js").status_code == 200


def test_cart_page_keeps_bag_script() -> None:
    response = TestClient(app).get("/cart")

    assert response.status_code == 200
    assert 'id="cart-root"' in response.text
    assert 'src="/js/bag.js"' in response.text


def test_checkout_rejects_cross_origin() -> None:
    response = TestClient(app).post("/checkout", data={"items": "[]"})

    assert response.status_code == 403


def test_checkout_re_renders_safe_fields_after_invalid_items() -> None:
    response = TestClient(app).post(
        "/checkout",
        data={"items": "not json", "email": "weaver@example.com", "name": "Ada Weaver"},
        headers={"origin": "http://testserver"},
    )

    assert response.status_code == 422
    assert "The bag could not be read." in response.text
    assert 'value="weaver@example.com"' in response.text
    assert 'value="Ada Weaver"' in response.text


def test_checkout_redirects_after_creating_an_order(monkeypatch) -> None:
    order_id = "11111111-1111-1111-1111-111111111111"
    monkeypatch.setattr("app.web.request_pool", lambda _request: object())
    monkeypatch.setattr("app.web.create_order", lambda *_args: {"orderId": order_id, "token": "private-token"})

    response = TestClient(app).post(
        "/checkout",
        data={
            "items": '[{"variantId":"22222222-2222-2222-2222-222222222222","quantity":1}]',
            "email": "weaver@example.com",
            "name": "Ada Weaver",
            "phone": "+919876543210",
            "address1": "1 Loom Lane",
            "city": "Guwahati",
            "state": "Assam",
            "postal_code": "781001",
            "country": "IN",
        },
        headers={"origin": "http://testserver"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/orders/{order_id}?token=private-token"


def test_invalid_order_link_is_not_found() -> None:
    response = TestClient(app).get(
        "/orders/00000000-0000-0000-0000-000000000000?exp=1&sig=bad"
    )

    assert response.status_code == 404


def test_pending_order_shows_payment_controls_only_with_all_credentials(monkeypatch) -> None:
    monkeypatch.setattr("app.web.request_pool", lambda _request: object())
    monkeypatch.setattr(
        "app.web.get_order",
        lambda *_args: {
            "order": {
                "id": "11111111-1111-1111-1111-111111111111",
                "status": "pending",
                "statusLabel": "Awaiting payment",
                "subtotalFormatted": "₹2,500.00",
                "shippingMinor": 0,
                "totalFormatted": "₹2,500.00",
                "shipName": "Ada Weaver",
                "shipAddress1": "1 Loom Lane",
                "shipAddress2": None,
                "shipCity": "Guwahati",
                "shipState": "Assam",
                "shipPostalCode": "781001",
                "shipCountry": "IN",
                "createdAt": "2026-09-01T00:00:00+00:00",
                "items": [],
            }
        },
    )
    client = TestClient(app)

    disabled = client.get("/orders/11111111-1111-1111-1111-111111111111?token=private-token")

    monkeypatch.setenv("RAZORPAY_KEY_ID", "key")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret")
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "webhook")
    enabled = client.get("/orders/11111111-1111-1111-1111-111111111111?token=private-token")

    assert 'id="pay-now"' not in disabled.text
    assert 'id="pay-now"' in enabled.text
    assert 'src="/js/pay.js"' in enabled.text
