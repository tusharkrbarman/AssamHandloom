from __future__ import annotations

import pytest
from httpx import AsyncClient
from lxml import html

pytest_plugins = ("tests.integration.storefront.test_catalog_routes",)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path", ["/", "/shop", "/collections/river-reed-gold", "/products/luit-dawn"]
)
async def test_public_pages_keep_one_page_heading_and_labelled_images(
    app_client: AsyncClient, seeded_catalog: None, path: str
) -> None:
    response = await app_client.get(path)
    document = html.fromstring(response.text)

    assert response.status_code == 200
    assert len(document.cssselect("main#main-content h1")) == 1
    assert all(image.get("alt") is not None for image in document.cssselect("img"))
    assert all(
        image.get("width") and image.get("height") for image in document.cssselect("img")
    )


@pytest.mark.anyio
async def test_shop_filter_controls_have_labels_and_grid_is_a_live_region(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    response = await app_client.get("/shop")
    document = html.fromstring(response.text)

    form = document.cssselect("form.catalogue-filters")
    assert len(form) == 1
    assert form[0].get("aria-label")
    assert len(document.cssselect('#product-grid[aria-live="polite"]')) == 1
    for control in form[0].cssselect("input, select"):
        assert control.get("id") or control.get("aria-label") or control.get("aria-labelledby")
