from __future__ import annotations

import pytest
from httpx import AsyncClient

pytest_plugins = ("tests.integration.storefront.test_catalog_routes",)


@pytest.mark.anyio
async def test_homepage_leads_to_collection_and_artisan_story(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    response = await app_client.get("/")

    assert response.status_code == 200
    assert "Woven by Assam. Worn with meaning." in response.text
    assert 'href="/shop"' in response.text
    assert "Meet the artisans" in response.text
    assert "Why Assam silk" in response.text
    assert "Email sign-up opens in a later phase" in response.text


@pytest.mark.anyio
async def test_product_page_exposes_commerce_and_provenance_facts(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    response = await app_client.get("/products/luit-dawn")

    assert response.status_code == 200
    for text in (
        "Muga",
        "Dimensions",
        "Care",
        "Motif",
        "Sample catalogue",
        "Checkout opens in the next build phase",
    ):
        assert text in response.text
    assert 'disabled' in response.text


@pytest.mark.anyio
async def test_shop_no_results_offers_recovery_and_get_filters_are_shareable(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    response = await app_client.get("/shop?search=not-a-weave")

    assert response.status_code == 200
    assert "No weaves matched your search." in response.text
    assert 'href="/shop"' in response.text
    assert 'method="get"' in response.text
    assert 'hx-push-url="true"' in response.text
    assert 'hx-target="#product-grid"' in response.text


@pytest.mark.anyio
async def test_cards_have_honest_unavailable_and_optional_image_states(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    response = await app_client.get("/shop")

    assert response.status_code == 200
    assert "Textile-colour study" in response.text
    assert "Available" in response.text
    assert "Sample catalogue" in response.text
    assert 'loading="lazy"' in response.text


@pytest.mark.anyio
async def test_pagination_preserves_filters_and_collection_context(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    response = await app_client.get(
        "/collections/river-reed-gold?silk_type=Muga&sort=price_desc&page_size=1"
    )

    assert response.status_code == 200
    assert (
        'href="/collections/river-reed-gold?silk_type=Muga&amp;sort=price_desc&amp;page_size=1&amp;page=2"'
        in response.text
    )
