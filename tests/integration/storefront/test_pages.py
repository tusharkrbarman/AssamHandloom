from __future__ import annotations

import pytest
from httpx import AsyncClient
from lxml import html

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
    assert "Verification pending" in response.text
    assert "General guidance" in response.text
    assert "River-line interpretation" not in response.text
    assert "Assam, India" not in response.text


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
    assert 'hx-target="#catalogue-results"' in response.text


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
    assert "Currently unavailable" in response.text
    assert 'data-secondary-image' in response.text


@pytest.mark.anyio
async def test_htmx_results_region_updates_cards_and_pagination_together(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    response = await app_client.get(
        "/shop?silk_type=Muga&page_size=1&search=Luit",
        headers={"HX-Request": "true"},
    )

    assert response.status_code == 200
    assert response.text.startswith('<section id="catalogue-results"')
    assert "Luit Dawn" in response.text
    assert "Muga Evening" not in response.text
    assert "Page 1 of" not in response.text
    assert "<!doctype html>" not in response.text.lower()


@pytest.mark.anyio
async def test_htmx_outer_swap_replaces_one_complete_filtered_results_region(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    path = "/shop?silk_type=Muga&silk_type=Pat&page_size=1&page=2"
    full = await app_client.get(path)
    fragment = await app_client.get(path, headers={"HX-Request": "true"})
    document = html.fromstring(full.text)
    old_region = document.cssselect("#catalogue-results")[0]
    replacement = html.fragment_fromstring(fragment.text)

    old_region.getparent().replace(old_region, replacement)

    assert 'hx-swap="outerHTML"' in full.text
    assert len(document.cssselect("#catalogue-results")) == 1
    assert len(document.cssselect("#product-grid")) == 1
    assert len(document.cssselect('#catalogue-results[aria-live="polite"]')) == 1
    assert "Page 2 of 3" in fragment.text
    assert (
        "silk_type=Muga&amp;silk_type=Pat&amp;page_size=1&amp;page=3" in fragment.text
    )


@pytest.mark.anyio
async def test_filter_form_exposes_supported_catalogue_filters(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    response = await app_client.get("/shop")

    assert response.status_code == 200
    for control in ("colour", "occasion", "silk_type", "sort", "price"):
        assert control in response.text
    assert "Weave (silk type)" in response.text


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
