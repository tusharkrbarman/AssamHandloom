from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.models import Collection, CollectionProduct, Product, PublicationState, Variant


@pytest.fixture
async def seeded_catalog(test_database_url: str) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(test_database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        await session.execute(delete(CollectionProduct))
        await session.execute(delete(Collection))
        await session.execute(delete(Variant))
        await session.execute(delete(Product))
        products = [
            _product(
                "luit-dawn",
                "Luit Dawn",
                "Muga",
                190_000,
                colour="Red",
                occasion="Wedding",
                featured_rank=3,
                created_at=_created_at(1),
                product_id=1,
            ),
            _product(
                "kopou-ivory",
                "Kopou Ivory",
                "Pat",
                180_000,
                colour="Ivory",
                occasion="Everyday",
                featured_rank=2,
                created_at=_created_at(3),
                product_id=2,
            ),
            _product(
                "muga-evening",
                "Muga Evening",
                "Muga",
                250_000,
                colour="Green",
                occasion="Wedding",
                featured_rank=1,
                created_at=_created_at(1),
                product_id=3,
            ),
            _product(
                "unpublished-weave",
                "Unpublished Weave",
                "Muga",
                99_000,
                state=PublicationState.DRAFT,
                colour="Red",
                occasion="Wedding",
            ),
        ]
        collection = Collection(
            id=uuid.uuid4(),
            slug="river-reed-gold",
            title="River, Reed & Gold",
            publication_state=PublicationState.PUBLISHED,
        )
        collection.collection_products.extend(
            [
                CollectionProduct(product=products[0], display_order=0),
                CollectionProduct(product=products[1], display_order=1),
                CollectionProduct(product=products[2], display_order=2),
            ]
        )
        session.add_all([*products, collection])
        await session.commit()
    await engine.dispose()


def _product(
    slug: str,
    title: str,
    silk_type: str,
    price_minor: int,
    *,
    state: PublicationState = PublicationState.PUBLISHED,
    colour: str | None = None,
    occasion: str | None = None,
    featured_rank: int = 0,
    created_at: datetime | None = None,
    product_id: int | None = None,
) -> Product:
    product = Product(
        id=uuid.UUID(int=product_id) if product_id is not None else uuid.uuid4(),
        slug=slug,
        title=title,
        silk_type=silk_type,
        colour=colour,
        occasion=occasion,
        publication_state=state,
        featured_rank=featured_rank,
        created_at=created_at,
    )
    product.variants.append(
        Variant(
            id=uuid.uuid4(),
            product_id=product.id,
            sku=f"sku-{slug}",
            price_minor=price_minor,
            currency="INR",
            publication_state=state,
            inventory_quantity=1,
        )
    )
    return product


def _created_at(days: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=days)


@pytest.mark.anyio
async def test_shop_filters_to_published_muga_products(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    response = await app_client.get("/shop?silk_type=Muga")

    assert response.status_code == 200
    assert "Luit Dawn" in response.text
    assert "Muga Evening" in response.text
    assert "Kopou Ivory" not in response.text
    assert "Unpublished Weave" not in response.text


@pytest.mark.anyio
async def test_catalogue_api_and_html_have_matching_filtered_titles(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    html = await app_client.get("/shop?silk_type=Muga&silk_type=Pat&sort=price_asc")
    api = await app_client.get(
        "/api/v1/catalog/products?silk_type=Muga&silk_type=Pat&sort=price_asc"
    )

    assert html.status_code == 200
    assert api.status_code == 200
    assert [item["title"] for item in api.json()["items"]] == [
        "Kopou Ivory",
        "Luit Dawn",
        "Muga Evening",
    ]
    for title in (item["title"] for item in api.json()["items"]):
        assert title in html.text
    assert "Unpublished Weave" not in api.text


@pytest.mark.anyio
async def test_search_normalizes_whitespace_and_page_size_is_clamped(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    response = await app_client.get(
        "/api/v1/catalog/products?search=%20%20LUIT%20%20DAWN%20&page_size=999"
    )

    assert response.status_code == 200
    assert response.json()["page_size"] == 24
    assert [item["slug"] for item in response.json()["items"]] == ["luit-dawn"]


@pytest.mark.anyio
async def test_invalid_sort_is_a_json_validation_error_but_html_uses_featured(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    api = await app_client.get("/api/v1/catalog/products?sort=not-a-sort")
    html = await app_client.get("/shop?sort=not-a-sort")

    assert api.status_code == 422
    assert api.json()["detail"] == "Invalid sort value"
    assert html.status_code == 200
    assert html.text.index("Luit Dawn") < html.text.index("Kopou Ivory")


@pytest.mark.anyio
async def test_hx_request_returns_only_grid_with_same_filter_semantics(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    response = await app_client.get("/shop?silk_type=Pat", headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert 'id="product-grid"' in response.text
    assert "Kopou Ivory" in response.text
    assert "Luit Dawn" not in response.text
    assert "<!doctype html>" not in response.text.lower()


@pytest.mark.anyio
async def test_collection_product_and_unknown_product_boundaries(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    collection = await app_client.get("/collections/river-reed-gold")
    product = await app_client.get("/products/luit-dawn")
    missing = await app_client.get("/products/not-a-saree")

    assert collection.status_code == 200
    assert "Luit Dawn" in collection.text
    assert "Muga Evening" in collection.text
    assert product.status_code == 200
    assert "Luit Dawn" in product.text
    assert missing.status_code == 404
    assert "We couldn’t find that weave" in missing.text
    assert 'href="/search"' in missing.text
    assert 'href="/collections"' in missing.text


@pytest.mark.anyio
async def test_collection_honours_repeated_filters_newest_order_and_htmx_parity(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    url = (
        "/collections/river-reed-gold?colour=Red&colour=Ivory&occasion=Wedding"
        "&occasion=Everyday&sort=newest&page_size=1"
    )
    full = await app_client.get(url)
    partial = await app_client.get(url, headers={"HX-Request": "true"})

    assert full.status_code == 200
    assert "Kopou Ivory" in full.text
    assert "Luit Dawn" not in full.text
    assert "Muga Evening" not in full.text
    assert 'id="product-grid"' in partial.text
    assert "Kopou Ivory" in partial.text
    assert "Luit Dawn" not in partial.text
    assert "<!doctype html>" not in partial.text.lower()


@pytest.mark.anyio
async def test_collection_pagination_has_bounds_and_stable_newest_ties(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    first = await app_client.get("/collections/river-reed-gold?sort=newest&page=0&page_size=1")
    repeated = await app_client.get("/collections/river-reed-gold?sort=newest&page=1&page_size=1")
    second = await app_client.get("/collections/river-reed-gold?sort=newest&page=2&page_size=1")
    repeated_second = await app_client.get(
        "/collections/river-reed-gold?sort=newest&page=2&page_size=1"
    )
    third = await app_client.get("/collections/river-reed-gold?sort=newest&page=3&page_size=1")

    assert first.status_code == 200
    assert first.text == repeated.text
    assert "Kopou Ivory" in first.text
    assert "Luit Dawn" in second.text
    assert second.text == repeated_second.text
    assert "Muga Evening" in third.text


@pytest.mark.anyio
async def test_collections_landing_is_a_safe_404_recovery_destination(
    app_client: AsyncClient, seeded_catalog: None
) -> None:
    response = await app_client.get("/collections")

    assert response.status_code == 200
    assert "River, Reed &amp; Gold" in response.text
