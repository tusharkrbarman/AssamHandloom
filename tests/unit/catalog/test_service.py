from __future__ import annotations

import uuid

import pytest

from app.catalog.models import ArtisanProfile, Product, PublicationState, Variant
from app.catalog.schemas import ProductCard
from app.catalog.service import CatalogService


@pytest.fixture
def catalog_service() -> CatalogService:
    return CatalogService()


@pytest.fixture
def draft_product() -> Product:
    return Product(
        id=uuid.uuid4(),
        slug="draft-luit",
        title="Draft Luit",
        silk_type="Muga",
        publication_state=PublicationState.DRAFT,
    )


def _product(state: PublicationState, variant_state: PublicationState) -> Product:
    product = Product(
        id=uuid.uuid4(),
        slug=f"{state.value}-{variant_state.value}",
        title="Luit Dawn",
        silk_type="Muga",
        publication_state=state,
    )
    product.variants.append(
        Variant(
            id=uuid.uuid4(),
            product_id=product.id,
            sku=f"SKU-{state.value}-{variant_state.value}",
            price_minor=1890000,
            currency="INR",
            publication_state=variant_state,
            inventory_quantity=1,
        )
    )
    return product


def test_product_card_formats_integer_minor_units() -> None:
    card = ProductCard(
        slug="luit-dawn",
        title="Luit Dawn",
        silk_type="Muga",
        artisan_name="Sample artisan",
        price_minor=1890000,
        currency="INR",
        available=True,
        primary_image=None,
    )

    assert card.display_price == "₹18,900"


def test_product_card_uses_iso_code_for_non_inr_currency() -> None:
    card = ProductCard(
        slug="luit-dawn",
        title="Luit Dawn",
        silk_type="Muga",
        artisan_name="Sample artisan",
        price_minor=1890000,
        currency="USD",
        available=True,
        primary_image=None,
    )

    assert card.display_price == "USD 18,900"


def test_draft_product_is_never_returned(
    catalog_service: CatalogService, draft_product: Product
) -> None:
    result = catalog_service.visible_product(draft_product, preview_enabled=True)

    assert result is None


def test_published_product_without_visible_variant_is_excluded(
    catalog_service: CatalogService,
) -> None:
    product = _product(PublicationState.PUBLISHED, PublicationState.DRAFT)

    assert catalog_service.visible_product(product, preview_enabled=False) is None


def test_preview_records_are_hidden_when_preview_is_disabled(
    catalog_service: CatalogService,
) -> None:
    product = _product(PublicationState.PREVIEW, PublicationState.PREVIEW)

    assert catalog_service.visible_product(product, preview_enabled=False) is None


def test_preview_records_are_visible_as_samples_when_preview_is_enabled(
    catalog_service: CatalogService,
) -> None:
    product = _product(PublicationState.PREVIEW, PublicationState.PREVIEW)
    product.artisan = ArtisanProfile(
        id=uuid.uuid4(),
        display_name="Sample artisan",
        is_sample=True,
    )

    card = catalog_service.to_product_card(product, preview_enabled=True)

    assert card is not None
    assert card.is_sample is True
    assert card.sample_label == "Sample"


def test_artisan_sample_status_propagates_to_product_card(catalog_service: CatalogService) -> None:
    product = _product(PublicationState.PUBLISHED, PublicationState.PUBLISHED)
    product.artisan = ArtisanProfile(
        id=uuid.uuid4(),
        display_name="Sample artisan",
        is_sample=True,
    )

    card = catalog_service.to_product_card(product, preview_enabled=False)

    assert card is not None
    assert card.is_sample is True
    assert card.sample_label == "Sample"
