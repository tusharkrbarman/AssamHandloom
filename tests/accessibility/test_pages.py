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
async def test_product_gallery_preserves_source_alt_and_loading_priority(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    response = await app_client.get("/products/luit-dawn")
    document = html.fromstring(response.text)
    gallery_images = document.cssselect(".product-detail__gallery img")

    assert len(gallery_images) == 2
    assert gallery_images[0].get("alt") == "First Muga silk detail"
    assert gallery_images[0].get("loading") is None
    assert gallery_images[1].get("alt") == "Muga silk in a warm red river-line weave"
    assert gallery_images[1].get("loading") == "lazy"


@pytest.mark.anyio
async def test_shop_filter_controls_have_labels_and_grid_is_a_live_region(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    response = await app_client.get("/shop")
    document = html.fromstring(response.text)

    form = document.cssselect("form.catalogue-filters")
    assert len(form) == 1
    assert form[0].get("aria-label")
    assert len(document.cssselect('#catalogue-results[aria-live="polite"]')) == 1
    for control in form[0].cssselect("input, select"):
        assert control.get("id") or control.get("aria-label") or control.get("aria-labelledby")


@pytest.mark.anyio
async def test_secondary_card_image_is_decorative_and_hover_scoped(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    response = await app_client.get("/shop")
    document = html.fromstring(response.text)
    css = (await app_client.get("/static/css/site.css")).text

    secondary = document.cssselect("[data-secondary-image]")
    assert len(secondary) == 1
    assert secondary[0].get("aria-hidden") == "true"
    assert secondary[0].get("alt") == ""
    assert "@media (hover: hover) and (pointer: fine)" in css
    primary = document.cssselect(".product-card__primary-image")
    assert primary[0].get("alt") == "Muga silk in a warm red river-line weave"
    assert secondary[0].get("src") != primary[0].get("src")
