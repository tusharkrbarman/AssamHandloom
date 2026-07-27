"""Validated, idempotent loader for the clearly labelled Phase 1 sample catalogue."""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.catalog.models import (
    ArtisanProfile,
    Product,
    ProductMedia,
    PublicationState,
    Variant,
)
from app.config import get_settings

APPROVED_TITLES = (
    "Luit Dawn",
    "Sualkuchi Gold",
    "Xorai Light",
    "Monsoon Reed",
    "Brahmaputra White",
    "Kopou Bloom",
    "Tea Garden Mist",
    "Japi Moon",
    "Eri Earth",
    "Ahin Loom",
    "River Reed",
    "Lac Horizon",
)
SILK_COUNTS = {"Muga": 4, "Pat": 4, "Eri": 2, "Silk blend": 2}


class CatalogueValidationError(ValueError):
    """Raised when a sample catalogue is incomplete or unsafe to load."""


@dataclass(frozen=True)
class SeedResult:
    products_created: int = 0
    products_updated: int = 0


def validate_catalogue(path: Path) -> dict[str, object]:
    """Read and validate every record before any database transaction begins."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CatalogueValidationError(f"cannot read sample catalogue: {error}") from error
    if not isinstance(raw, dict):
        raise CatalogueValidationError("catalogue root must be an object")
    _normalise_stable_identities(raw)
    artisans = raw.get("artisans")
    products = raw.get("products")
    if not isinstance(artisans, list) or not isinstance(products, list):
        raise CatalogueValidationError("catalogue requires artisan and product lists")
    if len(products) != len(APPROVED_TITLES):
        raise CatalogueValidationError("catalogue must contain exactly 12 products")
    _validate_artisans(artisans)
    _validate_products(products, len(artisans))
    return {"artisans": artisans, "products": products}


def _require_string(record: dict[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise CatalogueValidationError(f"{field} is required")
    return value


def _require_int(record: dict[str, object], field: str, *, positive: bool = False) -> int:
    value = record.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or (positive and value <= 0):
        qualifier = "a positive integer" if positive else "an integer"
        raise CatalogueValidationError(f"{field} must be {qualifier}")
    return value


def _normalise_identity(value: str) -> str:
    return " ".join(value.split()).casefold()


def _normalise_stable_identities(catalogue: dict[str, object]) -> None:
    """Canonicalise machine keys and trim display identities without changing product titles."""

    artisans = catalogue.get("artisans")
    products = catalogue.get("products")
    if isinstance(artisans, list):
        for artisan_raw in artisans:
            artisan = _as_object(artisan_raw, "artisan")
            name = artisan.get("display_name")
            if isinstance(name, str):
                artisan["display_name"] = " ".join(name.split())
    if isinstance(products, list):
        for product_raw in products:
            product = _as_object(product_raw, "product")
            slug = product.get("slug")
            if isinstance(slug, str):
                product["slug"] = slug.strip().lower()
            variant_raw = product.get("variant")
            if isinstance(variant_raw, dict):
                sku = variant_raw.get("sku")
                if isinstance(sku, str):
                    variant_raw["sku"] = sku.strip().upper()


def _as_object(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise CatalogueValidationError(f"{field} must be an object")
    return value


def _validate_artisans(artisans: list[object]) -> None:
    if not artisans:
        raise CatalogueValidationError("catalogue requires sample artisans")
    identities: set[str] = set()
    for artisan_raw in artisans:
        artisan = _as_object(artisan_raw, "artisan")
        for field in ("display_name", "biography", "location", "portrait_url"):
            _require_string(artisan, field)
        if artisan.get("is_sample") is not True:
            raise CatalogueValidationError("every artisan must be explicitly sample")
        identity = _normalise_identity(_require_string(artisan, "display_name"))
        if identity in identities:
            raise CatalogueValidationError("artisan identities must be unique")
        identities.add(identity)


def _validate_products(products: list[object], artisan_count: int) -> None:
    slugs: set[str] = set()
    skus: set[str] = set()
    titles: set[str] = set()
    silk_counts: dict[str, int] = {}
    featured_ranks: set[int] = set()
    for product_raw in products:
        product = _as_object(product_raw, "product")
        for field in ("slug", "title", "description", "silk_type", "colour", "occasion"):
            _require_string(product, field)
        slug = _require_string(product, "slug")
        title = _require_string(product, "title")
        if slug in slugs or title in titles:
            raise CatalogueValidationError("product handles and titles must be unique")
        slugs.add(slug)
        titles.add(title)
        if product.get("is_sample") is not True:
            raise CatalogueValidationError("every product must be explicitly sample")
        if product.get("publication_state") != PublicationState.PREVIEW.value:
            raise CatalogueValidationError("sample products must remain preview-only")
        featured_rank = _require_int(product, "featured_rank", positive=True)
        if featured_rank in featured_ranks:
            raise CatalogueValidationError("featured ranks must be unique")
        featured_ranks.add(featured_rank)
        artisan_index = _require_int(product, "artisan_index")
        if not 0 <= artisan_index < artisan_count:
            raise CatalogueValidationError("product artisan reference is invalid")
        silk_type = _require_string(product, "silk_type")
        silk_counts[silk_type] = silk_counts.get(silk_type, 0) + 1
        provenance = _as_object(product.get("provenance"), "provenance")
        if (
            provenance.get("is_sample") is not True
            or provenance.get("verification_state") != "unverified"
        ):
            raise CatalogueValidationError("provenance must be explicitly sample and unverified")
        media = product.get("media")
        if not isinstance(media, list) or not media:
            raise CatalogueValidationError("each product requires placeholder media")
        media_orders: set[int] = set()
        primary_count = 0
        for media_raw in media:
            item = _as_object(media_raw, "media")
            for field in ("url", "alt_text"):
                _require_string(item, field)
            display_order = _require_int(item, "display_order", positive=True)
            if display_order in media_orders:
                raise CatalogueValidationError("media display_order values must be unique")
            media_orders.add(display_order)
            if item.get("is_primary") is True:
                primary_count += 1
            if item.get("is_placeholder") is not True:
                raise CatalogueValidationError("every media item must be a placeholder")
        if primary_count != 1:
            raise CatalogueValidationError("each product requires exactly one primary media item")
        variant = _as_object(product.get("variant"), "variant")
        sku = _require_string(variant, "sku")
        if sku in skus:
            raise CatalogueValidationError("SKUs must be unique")
        skus.add(sku)
        _require_string(variant, "title")
        _require_int(variant, "price_minor", positive=True)
        _require_int(variant, "weight_grams", positive=True)
        if _require_int(variant, "inventory_quantity") < 0:
            raise CatalogueValidationError("inventory_quantity must not be negative")
        if variant.get("currency") != "INR":
            raise CatalogueValidationError("sample prices must be integer INR")
        if variant.get("publication_state") != PublicationState.PREVIEW.value:
            raise CatalogueValidationError("sample variants must remain preview-only")
    approved_titles = tuple(title for title in APPROVED_TITLES if title in titles)
    if approved_titles != APPROVED_TITLES:
        raise CatalogueValidationError("catalogue titles must use the approved twelve names")
    if silk_counts != SILK_COUNTS:
        raise CatalogueValidationError("catalogue must have the approved silk distribution")


async def load_sample_catalogue(session: AsyncSession, path: Path) -> SeedResult:
    """Create or update the deterministic sample records using stable slug and SKU keys."""

    catalogue = validate_catalogue(path)
    artisans_raw = catalogue["artisans"]
    products_raw = catalogue["products"]
    assert isinstance(artisans_raw, list)
    assert isinstance(products_raw, list)
    async with session.begin():
        source_slugs = [
            _require_string(_as_object(item, "product"), "slug") for item in products_raw
        ]
        previous_artisan_ids = (
            (
                await session.scalars(
                    select(Product.artisan_id).where(Product.slug.in_(source_slugs))
                )
            ).all()
        )
        stale_artisan_ids = {
            artisan_id for artisan_id in previous_artisan_ids if artisan_id is not None
        }
        artisans = await _upsert_artisans(session, artisans_raw)
        result = SeedResult()
        for product_raw in products_raw:
            product = _as_object(product_raw, "product")
            created = await _upsert_product(session, product, artisans)
            result = SeedResult(
                products_created=result.products_created + int(created),
                products_updated=result.products_updated + int(not created),
            )
        await session.flush()
        await _remove_unreferenced_seed_artisans(session, stale_artisan_ids)
    return result


async def _upsert_artisans(
    session: AsyncSession, artisans_raw: list[object]
) -> list[ArtisanProfile]:
    artisans: list[ArtisanProfile] = []
    for artisan_raw in artisans_raw:
        raw = _as_object(artisan_raw, "artisan")
        name = _require_string(raw, "display_name")
        artisan = await _find_sample_artisan(session, name)
        if artisan is None:
            artisan = ArtisanProfile(display_name=name)
            session.add(artisan)
        artisan.biography = _require_string(raw, "biography")
        artisan.location = _require_string(raw, "location")
        artisan.portrait_url = _require_string(raw, "portrait_url")
        artisan.is_sample = True
        artisans.append(artisan)
    await session.flush()
    return artisans


async def _find_sample_artisan(session: AsyncSession, name: str) -> ArtisanProfile | None:
    identity = _normalise_identity(name)
    candidates = list(
        (
            await session.scalars(
                select(ArtisanProfile).where(ArtisanProfile.is_sample.is_(True))
            )
        ).all()
    )
    return next(
        (
            candidate
            for candidate in candidates
            if _normalise_identity(candidate.display_name) == identity
        ),
        None,
    )


async def _upsert_product(
    session: AsyncSession, raw: dict[str, object], artisans: list[ArtisanProfile]
) -> bool:
    slug = _require_string(raw, "slug")
    product = await session.scalar(select(Product).where(Product.slug == slug))
    created = product is None
    if product is None:
        product = Product(slug=slug)
        session.add(product)
    product.title = _require_string(raw, "title")
    product.description = _require_string(raw, "description")
    product.silk_type = _require_string(raw, "silk_type")
    product.colour = _require_string(raw, "colour")
    product.occasion = _require_string(raw, "occasion")
    product.artisan = artisans[_require_int(raw, "artisan_index")]
    product.publication_state = PublicationState.PREVIEW
    product.featured_rank = _require_int(raw, "featured_rank", positive=True)
    await session.flush()
    await _replace_media(session, product, raw)
    await _upsert_variant(session, product, _as_object(raw.get("variant"), "variant"))
    return created


async def _replace_media(session: AsyncSession, product: Product, raw: dict[str, object]) -> None:
    media = raw["media"]
    assert isinstance(media, list)
    existing_media = list(
        (
            await session.scalars(
                select(ProductMedia).where(ProductMedia.product_id == product.id)
            )
        ).all()
    )
    for item in existing_media:
        await session.delete(item)
    if existing_media:
        await session.flush()
    for media_raw in media:
        media_data = _as_object(media_raw, "media")
        session.add(
            ProductMedia(
                product=product,
                url=_require_string(media_data, "url"),
                alt_text=_require_string(media_data, "alt_text"),
                display_order=_require_int(media_data, "display_order", positive=True),
                is_primary=media_data.get("is_primary") is True,
            )
        )


async def _upsert_variant(session: AsyncSession, product: Product, raw: dict[str, object]) -> None:
    sku = _require_string(raw, "sku")
    variant = await session.scalar(select(Variant).where(Variant.sku == sku))
    if variant is None:
        variant = Variant(product=product, sku=sku, price_minor=0)
        session.add(variant)
    elif variant.product_id != product.id:
        raise CatalogueValidationError("incoming SKU belongs to another product")
    variant.product = product
    variant.title = _require_string(raw, "title")
    variant.price_minor = _require_int(raw, "price_minor", positive=True)
    variant.currency = "INR"
    variant.weight_grams = _require_int(raw, "weight_grams", positive=True)
    variant.inventory_quantity = _require_int(raw, "inventory_quantity")
    variant.publication_state = PublicationState.PREVIEW
    await session.flush()
    stale_variants = list(
        (await session.scalars(select(Variant).where(Variant.product_id == product.id))).all()
    )
    for stale_variant in stale_variants:
        if (
            stale_variant.id != variant.id
            and stale_variant.publication_state is PublicationState.PREVIEW
        ):
            await session.delete(stale_variant)


async def _remove_unreferenced_seed_artisans(
    session: AsyncSession, artisan_ids: set[uuid.UUID]
) -> None:
    for artisan_id in artisan_ids:
        artisan = await session.get(ArtisanProfile, artisan_id)
        if artisan is None or not artisan.is_sample:
            continue
        reference = await session.scalar(
            select(Product.id).where(Product.artisan_id == artisan.id).limit(1)
        )
        if reference is None:
            await session.delete(artisan)


def run() -> None:
    """Load the bundled sample catalogue using the configured PostgreSQL database."""

    asyncio.run(_run())


async def _run() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as session:
            result = await load_sample_catalogue(
                session, Path(__file__).parents[1] / "data" / "river-reed-gold.json"
            )
    finally:
        await engine.dispose()
    print(f"sample catalogue: {result.products_created} created, {result.products_updated} updated")
