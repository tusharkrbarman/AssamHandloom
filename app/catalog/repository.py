from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import ColumnElement, Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, with_loader_criteria

from app.catalog.models import Collection, CollectionProduct, Product, PublicationState, Variant
from app.catalog.schemas import Page, ProductListQuery


class CatalogRepository:
    """PostgreSQL queries for public catalogue records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _visible_states(preview_enabled: bool) -> tuple[PublicationState, ...]:
        return (
            (PublicationState.PUBLISHED, PublicationState.PREVIEW)
            if preview_enabled
            else (PublicationState.PUBLISHED,)
        )

    @staticmethod
    def _products_with_visible_variants(
        query: ProductListQuery, preview_enabled: bool
    ) -> Select[tuple[Product]]:
        statement = select(Product).where(
            CatalogRepository._visible_product_clause(preview_enabled)
        )

        if query.search:
            statement = statement.where(func.lower(Product.title).contains(query.search.lower()))
        if query.silk_types:
            statement = statement.where(Product.silk_type.in_(query.silk_types))
        if query.colours:
            statement = statement.where(Product.colour.in_(query.colours))
        if query.occasions:
            statement = statement.where(Product.occasion.in_(query.occasions))
        if query.available_only:
            visible_states = CatalogRepository._visible_states(preview_enabled)
            statement = statement.where(
                select(Variant.id)
                .where(
                    Variant.product_id == Product.id,
                    Variant.publication_state.in_(visible_states),
                    Variant.inventory_quantity > 0,
                )
                .exists()
            )
        return statement

    @staticmethod
    def _visible_product_clause(preview_enabled: bool) -> ColumnElement[bool]:
        visible_states = CatalogRepository._visible_states(preview_enabled)
        visible_variant = (
            select(Variant.id)
            .where(Variant.product_id == Product.id, Variant.publication_state.in_(visible_states))
            .exists()
        )
        return and_(Product.publication_state.in_(visible_states), visible_variant)

    async def list_products(self, query: ProductListQuery, preview_enabled: bool) -> Page[Product]:
        """Return visible products and a stable total for the requested page."""

        statement = self._products_with_visible_variants(query, preview_enabled)
        total_statement = select(func.count()).select_from(statement.subquery())
        total = (await self._session.scalar(total_statement)) or 0
        visible_states = self._visible_states(preview_enabled)
        minimum_price = (
            select(func.min(Variant.price_minor))
            .where(Variant.product_id == Product.id, Variant.publication_state.in_(visible_states))
            .correlate(Product)
            .scalar_subquery()
        )

        if query.sort == "newest":
            statement = statement.order_by(Product.created_at.desc(), Product.id.asc())
        elif query.sort == "price_asc":
            statement = statement.order_by(minimum_price.asc(), Product.id.asc())
        elif query.sort == "price_desc":
            statement = statement.order_by(minimum_price.desc(), Product.id.asc())
        else:
            statement = statement.order_by(Product.featured_rank.desc(), Product.id.asc())

        statement = (
            statement.options(
                selectinload(Product.artisan),
                selectinload(Product.media),
                selectinload(Product.variants),
                with_loader_criteria(
                    Variant,
                    Variant.publication_state.in_(visible_states),
                    include_aliases=True,
                ),
            )
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
        products = list((await self._session.scalars(statement)).unique().all())
        return Page(items=products, total=total, page=query.page, page_size=query.page_size)

    async def get_product_by_slug(self, slug: str, preview_enabled: bool) -> Product | None:
        """Return a single visible product with only visible variants loaded."""

        query = ProductListQuery()
        statement = self._products_with_visible_variants(query, preview_enabled).where(
            Product.slug == slug
        )
        visible_states = self._visible_states(preview_enabled)
        statement = statement.options(
            selectinload(Product.artisan),
            selectinload(Product.media),
            selectinload(Product.variants),
            with_loader_criteria(
                Variant,
                Variant.publication_state.in_(visible_states),
                include_aliases=True,
            ),
        )
        return (await self._session.scalars(statement)).unique().one_or_none()

    async def list_collections(self, preview_enabled: bool) -> Sequence[Collection]:
        """Return visible collections in their explicit storefront order."""

        visible_states = self._visible_states(preview_enabled)
        visible_product = self._visible_product_clause(preview_enabled)
        statement = (
            select(Collection)
            .where(Collection.publication_state.in_(visible_states))
            .options(
                selectinload(Collection.collection_products)
                .selectinload(CollectionProduct.product)
                .selectinload(Product.artisan),
                selectinload(Collection.collection_products)
                .selectinload(CollectionProduct.product)
                .selectinload(Product.media),
                selectinload(Collection.collection_products)
                .selectinload(CollectionProduct.product)
                .selectinload(Product.variants),
                with_loader_criteria(
                    CollectionProduct,
                    CollectionProduct.product.has(visible_product),
                    include_aliases=True,
                ),
            )
            .order_by(Collection.display_order.asc(), Collection.id.asc())
            .execution_options(populate_existing=True)
        )
        return list((await self._session.scalars(statement)).unique().all())
