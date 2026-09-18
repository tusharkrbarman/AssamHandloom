from fastapi.testclient import TestClient

from app.links import create_order_link
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


def _order(status: str = "pending") -> dict[str, object]:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "status": status,
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


def test_home_renders_hero_and_published_catalogue_items(monkeypatch) -> None:
    monkeypatch.setattr("app.web.request_pool", lambda _request: object())
    monkeypatch.setattr("app.web.list_products", lambda _pool, _query: _page(PUBLISHED_PRODUCT))

    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert "Woven by Assam." in response.text
    assert "Golden Muga" in response.text


def test_home_keeps_the_accessibility_shell_and_expected_assets(monkeypatch) -> None:
    monkeypatch.setattr("app.web.request_pool", lambda _request: object())
    monkeypatch.setattr("app.web.list_products", lambda _pool, _query: _page(PUBLISHED_PRODUCT))

    response = TestClient(app).get("/")

    assert response.status_code == 200
    assert response.text.count('<main id="main-content" tabindex="-1">') == 1
    assert response.text.count('<a class="skip-link" href="#main-content">Skip to main content</a>') == 1
    assert response.text.count('<nav class="primary-nav" aria-label="Primary navigation">') == 1
    assert response.text.count('href="/css/site.css"') == 1
    assert response.text.count('src="/js/bag.js"') == 1
    assert response.text.count("<script") == 1


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


def test_arbitrary_missing_browser_path_renders_the_branded_not_found_page() -> None:
    response = TestClient(app).get("/definitely-missing")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert "We couldn’t find that weave" in response.text


def test_missing_product_renders_the_branded_not_found_page(monkeypatch) -> None:
    monkeypatch.setattr("app.web.request_pool", lambda _request: object())
    monkeypatch.setattr("app.web.get_product", lambda _pool, _slug: None)

    response = TestClient(app).get("/products/missing")

    assert response.status_code == 404
    assert "We couldn’t find that weave" in response.text


def test_search_route_uses_the_catalogue_service(monkeypatch) -> None:
    received = {}
    monkeypatch.setattr("app.web.request_pool", lambda _request: object())
    monkeypatch.setattr(
        "app.web.list_products",
        lambda _pool, query: (received.update(query=query) or _page(PUBLISHED_PRODUCT)),
    )

    response = TestClient(app).get("/search?q=Muga")

    assert response.status_code == 200
    assert received["query"].search == "Muga"
    assert "Search the catalogue" in response.text
    assert "Golden Muga" in response.text


def test_collections_route_uses_the_catalogue_service(monkeypatch) -> None:
    monkeypatch.setattr("app.web.request_pool", lambda _request: object())
    monkeypatch.setattr(
        "app.web.list_collections",
        lambda _pool: [{"id": "river", "slug": "river-edit", "title": "River Edit", "description": ""}],
    )

    response = TestClient(app).get("/collections")

    assert response.status_code == 200
    assert 'href="/collections/river-edit"' in response.text
    assert "River Edit" in response.text


def test_collection_route_uses_the_catalogue_services(monkeypatch) -> None:
    received = {}
    monkeypatch.setattr("app.web.request_pool", lambda _request: object())
    monkeypatch.setattr(
        "app.web.get_collection",
        lambda _pool, slug: {"id": "river", "slug": slug, "title": "River Edit", "description": ""},
    )
    monkeypatch.setattr(
        "app.web.list_products",
        lambda _pool, query: (received.update(query=query) or _page(PUBLISHED_PRODUCT)),
    )

    response = TestClient(app).get("/collections/river-edit")

    assert response.status_code == 200
    assert received["query"].collection_slug == "river-edit"
    assert "River Edit" in response.text
    assert "Golden Muga" in response.text


def test_product_page_keeps_its_css_hooks(monkeypatch) -> None:
    monkeypatch.setattr("app.web.request_pool", lambda _request: object())
    monkeypatch.setattr("app.web.get_product", lambda _pool, _slug: {**PUBLISHED_PRODUCT, "media": [], "variants": []})
    monkeypatch.setattr("app.web.list_products", lambda _pool, _query: _page(PUBLISHED_PRODUCT))

    response = TestClient(app).get("/products/golden-muga")

    assert response.status_code == 200
    assert 'class="product-detail"' in response.text
    assert 'class="product-detail__layout"' in response.text


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
    assert 'class="commerce-page"' in response.text
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


def test_checkout_page_keeps_its_css_hooks() -> None:
    response = TestClient(app).get("/checkout")

    assert response.status_code == 200
    assert 'class="commerce-page"' in response.text
    assert 'class="checkout-form"' in response.text
    assert 'class="checkout-grid"' in response.text
    assert 'class="checkout-summary"' in response.text


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


def test_order_page_forwards_a_valid_signed_link_to_get_order(monkeypatch) -> None:
    order = _order()
    secret = "s" * 32
    link = create_order_link(str(order["id"]), secret)
    expiry, signature = link.split("?", 1)[1].replace("exp=", "").split("&sig=")
    received: dict[str, object] = {}
    pool = object()
    monkeypatch.setenv("COOKIE_SIGNING_KEY", secret)
    monkeypatch.setattr(app.state, "db_pool", pool, raising=False)
    monkeypatch.setattr("app.web.verify_order_link", lambda *_args: (_ for _ in ()).throw(AssertionError()), raising=False)

    def fake_get_order(pool, order_id, token, expires_at, sig, signing_secret):
        received.update(
            pool=pool,
            order_id=order_id,
            token=token,
            expires_at=expires_at,
            signature=sig,
            signing_secret=signing_secret,
        )
        return {"order": order}

    monkeypatch.setattr("app.web.get_order", fake_get_order)

    response = TestClient(app).get(f"/orders/{link}")

    assert response.status_code == 200
    assert received["pool"] is pool
    assert received["order_id"] == order["id"]
    assert received["token"] is None
    assert received["expires_at"] == int(expiry)
    assert received["signature"] == signature
    assert received["signing_secret"] == secret


def test_order_page_passes_an_oversized_expiry_as_none(monkeypatch) -> None:
    received: dict[str, object] = {}
    monkeypatch.setattr(
        "app.web.get_order",
        lambda _pool, *_args: (received.update(expires_at=_args[2]) or {"order": _order()}),
    )

    response = TestClient(app).get(
        "/orders/11111111-1111-1111-1111-111111111111?token=private-token&exp=" + "9" * 5000
    )

    assert response.status_code == 200
    assert received["expires_at"] is None


def test_pending_order_shows_payment_controls_only_with_all_credentials(monkeypatch) -> None:
    order = _order()
    monkeypatch.setattr(
        "app.web.get_order",
        lambda *_args: {"order": order},
    )
    client = TestClient(app)

    disabled = client.get("/orders/11111111-1111-1111-1111-111111111111?token=private-token")

    monkeypatch.setenv("RAZORPAY_KEY_ID", "key")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret")
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "webhook")
    enabled = client.get("/orders/11111111-1111-1111-1111-111111111111?token=private-token")
    order["status"] = "paid"
    non_pending = client.get("/orders/11111111-1111-1111-1111-111111111111?token=private-token")

    assert 'id="pay-now"' not in disabled.text
    assert 'id="pay-now"' in enabled.text
    assert 'src="/js/pay.js"' in enabled.text
    assert 'id="pay-now"' not in non_pending.text
    assert 'src="/js/pay.js"' not in non_pending.text


def test_order_page_keeps_its_css_hooks(monkeypatch) -> None:
    monkeypatch.setattr("app.web.get_order", lambda *_args: {"order": _order()})

    response = TestClient(app).get("/orders/11111111-1111-1111-1111-111111111111?token=private-token")

    assert response.status_code == 200
    assert 'class="commerce-page order-confirmation"' in response.text
    assert 'class="bag-table"' in response.text
