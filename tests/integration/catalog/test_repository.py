from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.catalog.models import Collection, CollectionProduct, Product, PublicationState, Variant
from app.catalog.repository import CatalogRepository
from app.catalog.schemas import ProductListQuery


@pytest.fixture
async def session(test_database_url: str):
    engine = create_async_engine(test_database_url)
    async with AsyncSession(engine, expire_on_commit=False) as database_session:
        await database_session.execute(delete(CollectionProduct))
        await database_session.execute(delete(Collection))
        await database_session.execute(delete(Variant))
        await database_session.execute(delete(Product))
        await database_session.commit()
        yield database_session
    await engine.dispose()


def _product(slug: str, *, state: PublicationState = PublicationState.PUBLISHED) -> Product:
    product = Product(
        id=uuid.uuid4(),
        slug=slug,
        title=slug.replace("-", " ").title(),
        silk_type="Muga",
        publication_state=state,
    )
    product.variants.append(
        Variant(
            id=uuid.uuid4(),
            product_id=product.id,
            sku=f"sku-{slug}",
            price_minor=1890000,
            currency="INR",
            publication_state=state,
            inventory_quantity=1,
        )
    )
    return product


@pytest.mark.anyio
async def test_rejects_duplicate_product_slugs(session: AsyncSession) -> None:
    session.add_all([_product("luit-dawn"), _product("luit-dawn")])

    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.anyio
async def test_rejects_duplicate_variant_skus(session: AsyncSession) -> None:
    first = _product("luit-dawn")
    second = _product("brahmaputra-light")
    second.variants[0].sku = first.variants[0].sku
    session.add_all([first, second])

    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.anyio
async def test_rejects_negative_price_and_invalid_compare_at_price(session: AsyncSession) -> None:
    negative = _product("negative-price")
    negative.variants[0].price_minor = -1
    session.add(negative)

    with pytest.raises(IntegrityError):
        await session.commit()

    await session.rollback()
    invalid_compare_at = _product("invalid-compare-at")
    invalid_compare_at.variants[0].compare_at_price_minor = 1889999
    session.add(invalid_compare_at)

    with pytest.raises(IntegrityError):
        await session.commit()


@pytest.mark.anyio
async def test_repository_excludes_products_without_visible_variants(session: AsyncSession) -> None:
    hidden_variant = _product("hidden-variant")
    hidden_variant.variants[0].publication_state = PublicationState.DRAFT
    visible = _product("visible-variant")
    session.add_all([hidden_variant, visible])
    await session.commit()

    page = await CatalogRepository(session).list_products(ProductListQuery(), preview_enabled=False)

    assert page.total == 1
    assert [product.slug for product in page.items] == ["visible-variant"]


@pytest.mark.anyio
async def test_repository_hides_preview_unless_explicitly_enabled(session: AsyncSession) -> None:
    published = _product("published")
    preview = _product("preview", state=PublicationState.PREVIEW)
    draft = _product("draft", state=PublicationState.DRAFT)
    session.add_all([published, preview, draft])
    await session.commit()

    repository = CatalogRepository(session)
    disabled = await repository.list_products(
        ProductListQuery(sort="newest"), preview_enabled=False
    )
    enabled = await repository.list_products(ProductListQuery(sort="newest"), preview_enabled=True)

    assert {product.slug for product in disabled.items} == {"published"}
    assert {product.slug for product in enabled.items} == {"published", "preview"}


@pytest.mark.anyio
async def test_get_product_by_slug_applies_the_same_publication_rules(
    session: AsyncSession,
) -> None:
    published = _product("published")
    preview = _product("preview", state=PublicationState.PREVIEW)
    session.add_all([published, preview])
    await session.commit()

    repository = CatalogRepository(session)

    assert await repository.get_product_by_slug("preview", preview_enabled=False) is None
    assert (await repository.get_product_by_slug("preview", preview_enabled=True)).slug == "preview"
    assert (
        await repository.get_product_by_slug("published", preview_enabled=False)
    ).slug == "published"


@pytest.mark.anyio
async def test_collections_follow_preview_rules_and_display_order(session: AsyncSession) -> None:
    draft = Collection(
        id=uuid.uuid4(),
        slug="draft",
        title="Draft",
        publication_state=PublicationState.DRAFT,
        display_order=0,
    )
    published = Collection(
        id=uuid.uuid4(),
        slug="published",
        title="Published",
        publication_state=PublicationState.PUBLISHED,
        display_order=2,
    )
    preview = Collection(
        id=uuid.uuid4(),
        slug="preview",
        title="Preview",
        publication_state=PublicationState.PREVIEW,
        display_order=1,
    )
    session.add_all([draft, published, preview])
    await session.commit()

    repository = CatalogRepository(session)
    disabled = await repository.list_collections(preview_enabled=False)
    enabled = await repository.list_collections(preview_enabled=True)

    assert [collection.slug for collection in disabled] == ["published"]
    assert [collection.slug for collection in enabled] == ["preview", "published"]


@pytest.mark.anyio
async def test_repository_paginates_with_stable_ordering(session: AsyncSession) -> None:
    products = [_product(f"muga-{number:02d}") for number in range(3)]
    session.add_all(products)
    await session.commit()

    repository = CatalogRepository(session)
    first_page = await repository.list_products(
        ProductListQuery(sort="featured", page=1, page_size=2), preview_enabled=False
    )
    repeated_first_page = await repository.list_products(
        ProductListQuery(sort="featured", page=1, page_size=2), preview_enabled=False
    )
    second_page = await repository.list_products(
        ProductListQuery(sort="featured", page=2, page_size=2), preview_enabled=False
    )

    assert first_page.total == 3
    assert [product.id for product in first_page.items] == [
        product.id for product in repeated_first_page.items
    ]
    assert {product.id for product in first_page.items}.isdisjoint(
        {product.id for product in second_page.items}
    )
