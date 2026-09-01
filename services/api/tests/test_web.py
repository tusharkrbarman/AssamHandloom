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
