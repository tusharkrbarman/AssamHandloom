from __future__ import annotations

from collections.abc import Sequence

from app.catalog.models import Collection, Product, ProductMedia, PublicationState, Variant
from app.catalog.repository import CatalogRepository
from app.catalog.schemas import (
    Page,
    ProductCard,
    ProductDetail,
    ProductListQuery,
    ProductVariant,
)
from app.catalog.schemas import ProductMedia as PublicProductMedia


class CatalogService:
    """Maps visible catalogue records to the public Phase 1 read model."""

    def __init__(self, repository: CatalogRepository | None = None) -> None:
        self._repository = repository

    @staticmethod
    def _visible_states(preview_enabled: bool) -> tuple[PublicationState, ...]:
        return (
            (PublicationState.PUBLISHED, PublicationState.PREVIEW)
            if preview_enabled
            else (PublicationState.PUBLISHED,)
        )

    def visible_product(self, product: Product, preview_enabled: bool) -> Product | None:
        """Return a product only when it and at least one variant are visible."""

        visible_states = self._visible_states(preview_enabled)
        if product.publication_state not in visible_states or (
            not preview_enabled and product.is_sample
        ):
            return None
        if not self._visible_variants(product, preview_enabled):
            return None
        return product

    def to_product_card(self, product: Product, preview_enabled: bool) -> ProductCard | None:
        """Create a card from the cheapest visible variant of a visible product."""

        visible = self.visible_product(product, preview_enabled)
        if visible is None:
            return None
        visible_variants = self._visible_variants(visible, preview_enabled)
        variant = min(visible_variants, key=lambda candidate: candidate.price_minor)
        primary_media = self._primary_media(visible.media)
        artisan = visible.artisan
        is_sample = (
            visible.publication_state is PublicationState.PREVIEW
            or visible.is_sample
            or any(variant.is_sample for variant in visible_variants)
            or (artisan.is_sample if artisan is not None else False)
        )
        return ProductCard(
            slug=visible.slug,
            title=visible.title,
            silk_type=visible.silk_type,
            artisan_name=artisan.display_name if artisan is not None else None,
            price_minor=variant.price_minor,
            currency=variant.currency,
            available=any(candidate.inventory_quantity > 0 for candidate in visible_variants),
            media=self._public_media(visible.media),
            primary_media=self._to_public_media(primary_media) if primary_media else None,
            is_sample=is_sample,
        )

    def to_product_detail(self, product: Product, preview_enabled: bool) -> ProductDetail | None:
        """Create a public detail record while preserving publication boundaries."""

        visible = self.visible_product(product, preview_enabled)
        if visible is None:
            return None
        artisan = visible.artisan
        visible_variants = self._visible_variants(visible, preview_enabled)
        is_sample = (
            visible.publication_state is PublicationState.PREVIEW
            or visible.is_sample
            or any(variant.is_sample for variant in visible_variants)
            or (artisan.is_sample if artisan is not None else False)
        )
        variants = tuple(
            ProductVariant(
                sku=variant.sku,
                title=variant.title,
                price_minor=variant.price_minor,
                compare_at_price_minor=variant.compare_at_price_minor,
                currency=variant.currency,
                weight_grams=variant.weight_grams,
                available=variant.inventory_quantity > 0,
            )
            for variant in visible_variants
        )
        return ProductDetail(
            slug=visible.slug,
            title=visible.title,
            description=visible.description,
            silk_type=visible.silk_type,
            colour=visible.colour,
            occasion=visible.occasion,
            artisan_name=artisan.display_name if artisan is not None else None,
            media=self._public_media(visible.media),
            variants=variants,
            is_sample=is_sample,
            sample_label="Sample" if is_sample else None,
        )

    async def list_products(
        self, query: ProductListQuery, preview_enabled: bool
    ) -> Page[ProductCard]:
        """Load a page from the repository and project it into product cards."""

        repository = self._require_repository()
        products = await repository.list_products(query, preview_enabled)
        cards = [
            card
            for product in products.items
            if (card := self.to_product_card(product, preview_enabled)) is not None
        ]
        return Page(
            items=cards, total=products.total, page=products.page, page_size=products.page_size
        )

    async def get_product_by_slug(self, slug: str, preview_enabled: bool) -> ProductDetail | None:
        """Load and project one visible product detail record."""

        product = await self._require_repository().get_product_by_slug(slug, preview_enabled)
        return self.to_product_detail(product, preview_enabled) if product is not None else None

    async def list_collections(self, preview_enabled: bool) -> Sequence[Collection]:
        """Return visible collections in their configured display order."""

        return await self._require_repository().list_collections(preview_enabled)

    def _require_repository(self) -> CatalogRepository:
        if self._repository is None:
            raise RuntimeError("CatalogService requires a repository for database reads")
        return self._repository

    def _visible_variants(self, product: Product, preview_enabled: bool) -> list[Variant]:
        visible_states = self._visible_states(preview_enabled)
        return [
            variant
            for variant in product.variants
            if variant.publication_state in visible_states
            and (preview_enabled or not variant.is_sample)
        ]

    @staticmethod
    def _primary_media(media: Sequence[ProductMedia]) -> ProductMedia | None:
        return next((item for item in media if item.is_primary), media[0] if media else None)

    @staticmethod
    def _public_media(media: Sequence[ProductMedia]) -> tuple[PublicProductMedia, ...]:
        """Expose media in source display order for galleries and detail pages."""

        ordered = sorted(media, key=lambda item: item.display_order)
        return tuple(CatalogService._to_public_media(item) for item in ordered)

    @staticmethod
    def _to_public_media(media: ProductMedia) -> PublicProductMedia:
        return PublicProductMedia(
            url=media.url, alt_text=media.alt_text, display_order=media.display_order
        )
