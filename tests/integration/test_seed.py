from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.catalog.models import ArtisanProfile, Product, ProductMedia, PublicationState, Variant
from app.catalog.repository import CatalogRepository
from app.catalog.schemas import ProductListQuery
from app.seed import load_sample_catalogue


@pytest.fixture
def catalogue_path() -> Path:
    return Path(__file__).parents[2] / "data" / "river-reed-gold.json"


@pytest.fixture
async def db_session(test_database_url: str):  # type: ignore[no-untyped-def]
    engine = create_async_engine(test_database_url)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        await session.execute(delete(Product))
        await session.execute(delete(ArtisanProfile))
        await session.commit()
        yield session
    await engine.dispose()


@pytest.mark.anyio
async def test_seed_is_idempotent(db_session: AsyncSession, catalogue_path: Path) -> None:
    first = await load_sample_catalogue(db_session, catalogue_path)
    second = await load_sample_catalogue(db_session, catalogue_path)

    assert first.products_created == 12
    assert first.products_updated == 0
    assert second.products_created == 0
    assert second.products_updated == 12


@pytest.mark.anyio
async def test_sample_records_cannot_be_published(
    db_session: AsyncSession, catalogue_path: Path
) -> None:
    await load_sample_catalogue(db_session, catalogue_path)

    products = await CatalogRepository(db_session).list_products(
        query=ProductListQuery(),
        preview_enabled=False,
    )

    assert products.items == []


@pytest.mark.anyio
async def test_seeded_records_are_complete_and_explicitly_sample(
    db_session: AsyncSession, catalogue_path: Path
) -> None:
    await load_sample_catalogue(db_session, catalogue_path)
    products = list(
        (await db_session.scalars(select(Product).order_by(Product.featured_rank))).all()
    )
    variants = list((await db_session.scalars(select(Variant))).all())
    artisans = list((await db_session.scalars(select(ArtisanProfile))).all())
    media = list((await db_session.scalars(select(ProductMedia))).all())

    assert len(products) == 12
    assert {product.silk_type for product in products} == {"Muga", "Pat", "Eri", "Silk blend"}
    assert sum(product.silk_type == "Muga" for product in products) == 4
    assert sum(product.silk_type == "Pat" for product in products) == 4
    assert sum(product.silk_type == "Eri" for product in products) == 2
    assert sum(product.silk_type == "Silk blend" for product in products) == 2
    assert len({product.slug for product in products}) == 12
    assert len({variant.sku for variant in variants}) == 12
    assert all(product.publication_state is PublicationState.PREVIEW for product in products)
    assert all(variant.publication_state is PublicationState.PREVIEW for variant in variants)
    assert all(artisan.is_sample for artisan in artisans)
    assert len(media) >= 12
    assert all("sample placeholder" in (item.alt_text or "").lower() for item in media)
    assert all(
        variant.currency == "INR" and isinstance(variant.price_minor, int) for variant in variants
    )
    assert all(
        variant.price_minor > 0 and variant.weight_grams and variant.inventory_quantity >= 0
        for variant in variants
    )
    assert all(product.description and product.colour and product.occasion for product in products)
    assert await db_session.scalar(select(func.count()).select_from(Product)) == 12
