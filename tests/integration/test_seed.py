from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.catalog.models import ArtisanProfile, Product, ProductMedia, PublicationState, Variant
from app.catalog.repository import CatalogRepository
from app.catalog.schemas import ProductListQuery
from app.seed import CatalogueValidationError, SeedCollisionError, load_sample_catalogue


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
    assert all(product.is_sample for product in products)
    assert all(variant.is_sample for variant in variants)
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


def _mutated_catalogue(
    tmp_path: Path, mutate: Callable[[dict[str, Any]], object]
) -> Path:
    source_path = Path(__file__).parents[2] / "data" / "river-reed-gold.json"
    catalogue = json.loads(source_path.read_text())
    mutate(catalogue)
    path = tmp_path / "mutated-catalogue.json"
    path.write_text(json.dumps(catalogue), encoding="utf-8")
    return path


@pytest.mark.anyio
async def test_reseed_replaces_a_changed_sample_sku_without_stale_variants(
    db_session: AsyncSession, catalogue_path: Path, tmp_path: Path
) -> None:
    await load_sample_catalogue(db_session, catalogue_path)
    old_sku = "RRG-MUGA-001"
    new_sku = "RRG-MUGA-099"
    updated_path = _mutated_catalogue(
        tmp_path, lambda catalogue: catalogue["products"][0]["variant"].update({"sku": new_sku})
    )

    result = await load_sample_catalogue(db_session, updated_path)
    variants = list((await db_session.scalars(select(Variant))).all())

    assert result.products_created == 0
    assert result.products_updated == 12
    assert len(variants) == 12
    assert {variant.sku for variant in variants}.isdisjoint({old_sku})
    assert new_sku in {variant.sku for variant in variants}
    assert all(variant.publication_state is PublicationState.PREVIEW for variant in variants)


@pytest.mark.anyio
async def test_reseed_removes_unreferenced_renamed_sample_artisan_but_keeps_shared_profiles(
    db_session: AsyncSession, catalogue_path: Path, tmp_path: Path
) -> None:
    await load_sample_catalogue(db_session, catalogue_path)
    old_name = "Sample artisan A"
    shared = ArtisanProfile(display_name="Shared sample profile", is_sample=True)
    unrelated = Product(
        slug="unrelated-sample",
        title="Unrelated sample",
        silk_type="Muga",
        artisan=shared,
        publication_state=PublicationState.DRAFT,
    )
    db_session.add(unrelated)
    await db_session.commit()
    updated_path = _mutated_catalogue(
        tmp_path,
        lambda catalogue: catalogue["artisans"][0].update(
            {"display_name": "Renamed sample artisan"}
        ),
    )

    await load_sample_catalogue(db_session, updated_path)
    artisan_names = set((await db_session.scalars(select(ArtisanProfile.display_name))).all())

    assert old_name not in artisan_names
    assert "Renamed sample artisan" in artisan_names
    assert "Shared sample profile" in artisan_names


@pytest.mark.anyio
async def test_duplicate_media_order_is_rejected_before_any_database_writes(
    db_session: AsyncSession, catalogue_path: Path, tmp_path: Path
) -> None:
    invalid_path = _mutated_catalogue(
        tmp_path,
        lambda catalogue: catalogue["products"][0]["media"].append(
            copy.deepcopy(catalogue["products"][0]["media"][0])
        ),
    )

    with pytest.raises(CatalogueValidationError, match="display_order"):
        await load_sample_catalogue(db_session, invalid_path)

    assert await db_session.scalar(select(func.count()).select_from(Product)) == 0


@pytest.mark.anyio
async def test_case_only_seed_identity_changes_update_without_duplication(
    db_session: AsyncSession, catalogue_path: Path, tmp_path: Path
) -> None:
    await load_sample_catalogue(db_session, catalogue_path)
    updated_path = _mutated_catalogue(
        tmp_path,
        lambda catalogue: (
            catalogue["products"][0].update({"slug": "LUIT-DAWN"}),
            catalogue["products"][0]["variant"].update({"sku": "rrg-muga-001"}),
            catalogue["artisans"][0].update({"display_name": " sample ARTISAN a "}),
        ),
    )

    result = await load_sample_catalogue(db_session, updated_path)
    products = list((await db_session.scalars(select(Product))).all())
    variants = list((await db_session.scalars(select(Variant))).all())
    artisans = list((await db_session.scalars(select(ArtisanProfile))).all())

    assert result.products_created == 0
    assert result.products_updated == 12
    assert len(products) == 12
    assert len(variants) == 12
    assert {product.slug for product in products} >= {"luit-dawn"}
    assert {variant.sku for variant in variants} >= {"RRG-MUGA-001"}
    assert "Sample artisan A" in {artisan.display_name for artisan in artisans}


@pytest.mark.parametrize(
    "state", [PublicationState.DRAFT, PublicationState.PREVIEW, PublicationState.PUBLISHED]
)
@pytest.mark.anyio
async def test_non_sample_product_slug_collision_is_unchanged(
    db_session: AsyncSession, catalogue_path: Path, state: PublicationState
) -> None:
    artisan = ArtisanProfile(display_name="Verified artisan", is_sample=False)
    product = Product(
        slug="luit-dawn",
        title="Verified live product",
        silk_type="Muga",
        artisan=artisan,
        publication_state=state,
        is_sample=False,
    )
    product.media.append(
        ProductMedia(
            url="https://example.test/live.jpg",
            alt_text="Live",
            is_primary=True,
        )
    )
    db_session.add(product)
    await db_session.commit()

    with pytest.raises(SeedCollisionError, match="product slug"):
        await load_sample_catalogue(db_session, catalogue_path)

    persisted = await db_session.scalar(select(Product).where(Product.slug == "luit-dawn"))
    assert persisted is not None
    await db_session.refresh(persisted, attribute_names=["artisan", "media"])
    assert persisted.title == "Verified live product"
    assert persisted.publication_state is state
    assert persisted.is_sample is False
    assert persisted.artisan is not None and persisted.artisan.display_name == "Verified artisan"
    assert [media.url for media in persisted.media] == ["https://example.test/live.jpg"]
    assert await db_session.scalar(select(func.count()).select_from(Product)) == 1


@pytest.mark.anyio
async def test_non_sample_published_variant_sku_collision_is_unchanged(
    db_session: AsyncSession, catalogue_path: Path
) -> None:
    product = Product(slug="verified-live", title="Verified live", silk_type="Pat", is_sample=False)
    db_session.add(
        Variant(
            product=product,
            sku="RRG-MUGA-001",
            price_minor=999,
            currency="INR",
            publication_state=PublicationState.PUBLISHED,
            is_sample=False,
        )
    )
    await db_session.commit()

    with pytest.raises(SeedCollisionError, match="variant SKU"):
        await load_sample_catalogue(db_session, catalogue_path)

    persisted = await db_session.scalar(select(Variant).where(Variant.sku == "RRG-MUGA-001"))
    assert persisted is not None
    assert persisted.price_minor == 999
    assert persisted.compare_at_price_minor is None
    assert persisted.inventory_quantity == 0
    assert persisted.publication_state is PublicationState.PUBLISHED
    assert persisted.is_sample is False
    assert await db_session.scalar(select(func.count()).select_from(Product)) == 1


@pytest.mark.anyio
async def test_unrelated_preview_variant_on_sample_product_survives_sku_evolution(
    db_session: AsyncSession, catalogue_path: Path, tmp_path: Path
) -> None:
    await load_sample_catalogue(db_session, catalogue_path)
    product = await db_session.scalar(select(Product).where(Product.slug == "luit-dawn"))
    assert product is not None
    unrelated = Variant(
        product=product,
        sku="UNRELATED-PREVIEW",
        price_minor=1,
        currency="INR",
        publication_state=PublicationState.PREVIEW,
        is_sample=False,
    )
    db_session.add(unrelated)
    await db_session.commit()
    updated_path = _mutated_catalogue(
        tmp_path,
        lambda catalogue: catalogue["products"][0]["variant"].update({"sku": "RRG-MUGA-099"}),
    )

    await load_sample_catalogue(db_session, updated_path)

    persisted = await db_session.scalar(
        select(Variant).where(Variant.sku == "UNRELATED-PREVIEW")
    )
    assert persisted is not None
    assert persisted.is_sample is False
    assert persisted.publication_state is PublicationState.PREVIEW


@pytest.mark.anyio
async def test_case_insensitive_legacy_product_slug_collision_writes_nothing(
    db_session: AsyncSession, catalogue_path: Path
) -> None:
    db_session.add(
        Product(
            slug="LUIT-DAWN",
            title="Legacy live product",
            silk_type="Muga",
            is_sample=False,
        )
    )
    await db_session.commit()

    with pytest.raises(SeedCollisionError, match="product slug"):
        await load_sample_catalogue(db_session, catalogue_path)

    assert await db_session.scalar(select(func.count()).select_from(Product)) == 1


@pytest.mark.anyio
async def test_case_insensitive_legacy_variant_sku_collision_writes_nothing(
    db_session: AsyncSession, catalogue_path: Path
) -> None:
    product = Product(slug="legacy", title="Legacy", silk_type="Pat", is_sample=False)
    db_session.add(
        Variant(
            product=product,
            sku="rrg-muga-001",
            price_minor=55,
            currency="INR",
            is_sample=False,
        )
    )
    await db_session.commit()

    with pytest.raises(SeedCollisionError, match="variant SKU"):
        await load_sample_catalogue(db_session, catalogue_path)

    assert await db_session.scalar(select(func.count()).select_from(Product)) == 1
    assert await db_session.scalar(select(func.count()).select_from(Variant)) == 1


@pytest.mark.anyio
async def test_postgresql_enforces_canonical_slug_and_sku_uniqueness(
    db_session: AsyncSession, catalogue_path: Path
) -> None:
    await load_sample_catalogue(db_session, catalogue_path)
    db_session.add(
        Product(slug="LUIT-DAWN", title="Case collision", silk_type="Muga", is_sample=False)
    )

    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()

    product = Product(slug="canonical-variant-owner", title="Owner", silk_type="Pat")
    db_session.add(product)
    db_session.add(
        Variant(product=product, sku="rrg-muga-001", price_minor=1, currency="INR")
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.anyio
async def test_unrelated_integrity_error_is_not_translated_to_seed_collision(
    db_session: AsyncSession, catalogue_path: Path
) -> None:
    constraint_name = "ck_test_seed_title_rejection"
    await db_session.execute(
        text(
            f"ALTER TABLE products ADD CONSTRAINT {constraint_name} "
            "CHECK (title <> 'Luit Dawn')"
        )
    )
    await db_session.commit()

    try:
        with pytest.raises(IntegrityError) as captured:
            await load_sample_catalogue(db_session, catalogue_path)

        diagnostic = getattr(captured.value.orig, "diag", None)
        assert getattr(diagnostic, "constraint_name", None) == constraint_name
        assert await db_session.scalar(select(func.count()).select_from(Product)) == 0
    finally:
        await db_session.rollback()
        await db_session.execute(
            text(f"ALTER TABLE products DROP CONSTRAINT IF EXISTS {constraint_name}")
        )
        await db_session.commit()
