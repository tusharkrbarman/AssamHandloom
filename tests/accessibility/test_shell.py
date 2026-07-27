from __future__ import annotations

import pytest
from httpx import AsyncClient
from lxml import html


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
