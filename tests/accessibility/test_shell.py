from __future__ import annotations

from urllib.parse import urlparse

import pytest
from httpx import ASGITransport, AsyncClient
from lxml import html

from app.config import Settings
from app.main import create_app


@pytest.fixture
async def rendered_home(app_client: AsyncClient) -> html.HtmlElement:
    response = await app_client.get("/")

    assert response.status_code == 200
    return html.fromstring(response.text)


@pytest.mark.anyio
async def test_shell_has_one_main_landmark_and_skip_target(
    rendered_home: html.HtmlElement,
) -> None:
    assert len(rendered_home.cssselect("main#main-content")) == 1
    assert len(rendered_home.cssselect('a[href="#main-content"]')) == 1
    assert len(rendered_home.cssselect("main#main-content h1")) == 1


@pytest.mark.anyio
async def test_shell_has_labelled_navigation_search_and_forms(
    rendered_home: html.HtmlElement,
) -> None:
    navigation = rendered_home.cssselect("nav")
    assert navigation
    assert all(item.get("aria-label") or item.get("aria-labelledby") for item in navigation)

    search = rendered_home.cssselect('form[role="search"]')
    assert len(search) == 1
    assert search[0].cssselect("label")
    for control in rendered_home.cssselect("input, select, textarea"):
        assert control.get("aria-label") or control.get("aria-labelledby") or control.get("id")


@pytest.mark.anyio
async def test_shell_controls_and_document_order_are_accessible(
    rendered_home: html.HtmlElement,
) -> None:
    for button in rendered_home.cssselect("button"):
        assert button.text_content().strip() or button.get("aria-label")
    for image in rendered_home.cssselect("img"):
        assert image.get("alt") is not None
    assert not rendered_home.cssselect('[tabindex]:not([tabindex="-1"]):not([tabindex="0"])')

    landmarks = rendered_home.cssselect("body > header, body > main, body > footer")
    assert [landmark.tag for landmark in landmarks] == ["header", "main", "footer"]


def _assert_complete_shell(document: html.HtmlElement) -> None:
    assert len(document.cssselect("main#main-content")) == 1
    assert len(document.cssselect("main#main-content h1")) == 1
    landmarks = document.cssselect("body > header, body > main, body > footer")
    assert [item.tag for item in landmarks] == [
        "header",
        "main",
        "footer",
    ]
    navigation = document.cssselect("nav")
    assert all(item.get("aria-label") or item.get("aria-labelledby") for item in navigation)
    for control in document.cssselect("input, select, textarea"):
        control_id = control.get("id")
        labels = document.cssselect(f'label[for="{control_id}"]') if control_id else []
        assert labels or control.get("aria-label") or control.get("aria-labelledby")
    assert all(image.get("alt") is not None for image in document.cssselect("img"))


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/", "/shop", "/collections", "/products/not-a-saree"])
async def test_full_rendered_pages_keep_the_accessible_shell(
    app_client: AsyncClient, path: str
) -> None:
    response = await app_client.get(path)

    assert response.status_code in {200, 404}
    _assert_complete_shell(html.fromstring(response.text))


@pytest.mark.anyio
async def test_safe_500_response_keeps_the_branded_accessible_shell() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://postgres@127.0.0.1:1/luit_loom_unreachable",
        secret_key="test-secret-key-that-is-long-enough",
        environment="test",
        public_base_url="https://store.example.test",
    )
    app = create_app(settings)

    @app.get("/__test-boom")
    async def test_boom() -> None:
        raise RuntimeError("test-only failure")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/__test-boom")
    await app.state.engine.dispose()

    assert response.status_code == 500
    assert "Our loom needs a moment" in response.text
    _assert_complete_shell(html.fromstring(response.text))


@pytest.mark.anyio
async def test_canonical_uses_configured_origin_not_the_request_host(
    app_client: AsyncClient,
) -> None:
    response = await app_client.get("/shop?sort=newest", headers={"Host": "attacker.example"})

    document = html.fromstring(response.text)
    canonical = document.cssselect('link[rel="canonical"]')
    assert len(canonical) == 1
    assert canonical[0].get("href") == "http://testserver/shop"


@pytest.mark.anyio
async def test_local_assets_and_no_javascript_navigation_fallback(app_client: AsyncClient) -> None:
    response = await app_client.get("/")
    document = html.fromstring(response.text)
    script_sources = [script.get("src") for script in document.cssselect("script[src]")]
    primary_links = document.cssselect('nav[aria-label="Primary navigation"] a')
    css = await app_client.get("/static/css/site.css")
    htmx = await app_client.get("/static/vendor/htmx-2.0.4.min.js")

    assert any(
        source and source.endswith("/static/vendor/htmx-2.0.4.min.js")
        for source in script_sources
    )
    assert all(source and urlparse(source).path.startswith("/static/") for source in script_sources)
    assert len(primary_links) == 5
    assert {link.get("href") for link in primary_links} >= {"/shop", "/artisans"}
    assert {
        link.get("href") for link in document.cssselect('nav[aria-label="Footer navigation"] a')
    } == {
        "/pages/silk-guide",
        "/pages/care",
        "/pages/shipping",
        "/pages/returns",
        "/pages/contact",
        "/pages/faq",
    }
    assert "nth-child" not in css.text
    assert htmx.status_code == 200
    assert "htmx" in htmx.text.lower()


@pytest.mark.anyio
async def test_disclosure_markup_and_motion_safe_control_styles(app_client: AsyncClient) -> None:
    response = await app_client.get("/")
    document = html.fromstring(response.text)
    trigger = document.cssselect("[data-disclosure-button]")
    panel = document.cssselect("#mobile-navigation")
    backdrop = document.cssselect("[data-disclosure-backdrop]")
    css = await app_client.get("/static/css/site.css")
    script = await app_client.get("/static/js/site.js")

    assert len(trigger) == 1
    assert trigger[0].get("aria-expanded") == "false"
    assert trigger[0].get("aria-controls") == "mobile-navigation"
    assert len(panel) == 1 and panel[0].get("hidden") is not None
    assert len(backdrop) == 1 and backdrop[0].get("hidden") is not None
    assert ".wordmark" in css.text and "min-height: 2.75rem" in css.text
    assert "prefers-reduced-motion: reduce" in css.text
    assert "data-disclosure-button" in script.text
    assert 'panel.hidden = false' in script.text
    assert 'trigger.setAttribute("aria-expanded", "true")' in script.text
    assert 'backdrop.hidden = false' in script.text
    assert 'panel.hidden = true' in script.text
    assert 'trigger.setAttribute("aria-expanded", "false")' in script.text
    assert "trigger.focus()" in script.text
    assert 'event.key === "Escape"' in script.text
    assert "data-disclosure-backdrop" in script.text
