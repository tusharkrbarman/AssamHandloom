from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.sql import func

from app.db import Base


class PublicationState(StrEnum):
    """Publication states recognised by the public catalogue."""

    DRAFT = "draft"
    PREVIEW = "preview"
    PUBLISHED = "published"


publication_state_type = SqlEnum(
    PublicationState,
    name="publication_state",
    native_enum=False,
    values_callable=lambda states: [state.value for state in states],
    create_constraint=True,
)

ISO_4217_CODES = frozenset(
    "AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BOV BRL "
    "BSD BTN BWP BYN BZD CAD CDF CHE CHF CHW CLF CLP CNY COP COU CRC CUC CUP CVE CZK DJF "
    "DKK DOP DZD EGP ERN ETB EUR FJD FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HRK HTG "
    "HUF IDR ILS INR IQD IRR ISK JMD JOD JPY KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP "
    "LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP MRU MUR MVR MWK MXN MXV MYR MZN NAD NGN "
    "NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR RON RSD RUB RWF SAR SBD SCR SDG "
    "SEK SGD SHP SLE SLL SOS SRD SSP STN SVC SYP SZL THB TJS TMT TND TOP TRY TTD TWD TZS "
    "UAH UGX USD USN UYI UYU UYW UZS VED VES VND VUV WST XAF XAG XAU XBA XBB XBC XBD XCD "
    "XDR XOF XPD XPF XPT XSU XTS XUA XXX YER ZAR ZMW ZWL".split()
)


class Timestamped:
    """Columns shared by catalogue records that are edited over time."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ArtisanProfile(Timestamped, Base):
    """Approved, public-facing artisan information only."""

    __tablename__ = "artisan_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    biography: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(160), nullable=True)
    portrait_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_sample: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    products: Mapped[list[Product]] = relationship(back_populates="artisan")


class Product(Timestamped, Base):
    """A handloom product and its public catalogue content."""

    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    silk_type: Mapped[str] = mapped_column(String(80), nullable=False)
    colour: Mapped[str | None] = mapped_column(String(80), nullable=True)
    occasion: Mapped[str | None] = mapped_column(String(80), nullable=True)
    artisan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artisan_profiles.id", ondelete="SET NULL"), nullable=True
    )
    publication_state: Mapped[PublicationState] = mapped_column(
        publication_state_type,
        nullable=False,
        default=PublicationState.DRAFT,
        server_default="draft",
    )
    featured_rank: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    artisan: Mapped[ArtisanProfile | None] = relationship(back_populates="products")
    variants: Mapped[list[Variant]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="Variant.price_minor"
    )
    media: Mapped[list[ProductMedia]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductMedia.display_order",
    )
    collection_products: Mapped[list[CollectionProduct]] = relationship(back_populates="product")


class Variant(Timestamped, Base):
    """A purchasable product variant with immutable Phase 1 inventory data."""

    __tablename__ = "variants"
    __table_args__ = (
        CheckConstraint("price_minor >= 0", name="ck_variants_price_minor_non_negative"),
        CheckConstraint(
            "compare_at_price_minor IS NULL OR compare_at_price_minor >= price_minor",
            name="ck_variants_compare_at_price_not_less_than_price",
        ),
        CheckConstraint(
            "weight_grams IS NULL OR weight_grams >= 0", name="ck_variants_weight_non_negative"
        ),
        CheckConstraint("inventory_quantity >= 0", name="ck_variants_inventory_non_negative"),
        CheckConstraint(
            "currency ~ '^[A-Z]{3}$'",
            name="ck_variants_currency_uppercase_format",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    sku: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    price_minor: Mapped[int] = mapped_column(Integer, nullable=False)
    compare_at_price_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="INR", server_default="INR"
    )
    weight_grams: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inventory_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    publication_state: Mapped[PublicationState] = mapped_column(
        publication_state_type,
        nullable=False,
        default=PublicationState.DRAFT,
        server_default="draft",
    )

    product: Mapped[Product] = relationship(back_populates="variants")

    @validates("currency")
    def validate_currency(self, _: str, value: str) -> str:
        """Require a current, uppercase ISO 4217 currency code at the write boundary."""

        if value not in ISO_4217_CODES:
            raise ValueError("currency must be an uppercase ISO 4217 code")
        return value


class Collection(Timestamped, Base):
    """A manually ordered, publishable group of products."""

    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_state: Mapped[PublicationState] = mapped_column(
        publication_state_type,
        nullable=False,
        default=PublicationState.DRAFT,
        server_default="draft",
    )
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    collection_products: Mapped[list[CollectionProduct]] = relationship(
        back_populates="collection",
        cascade="all, delete-orphan",
        order_by="CollectionProduct.display_order",
    )


class CollectionProduct(Base):
    """Membership and display order for a product within a collection."""

    __tablename__ = "collection_products"
    __table_args__ = (
        UniqueConstraint(
            "collection_id", "product_id", name="uq_collection_products_collection_product"
        ),
        UniqueConstraint(
            "collection_id", "display_order", name="uq_collection_products_collection_order"
        ),
    )

    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    collection: Mapped[Collection] = relationship(back_populates="collection_products")
    product: Mapped[Product] = relationship(back_populates="collection_products")


class ProductMedia(Timestamped, Base):
    """A public product image and its explicit display order."""

    __tablename__ = "product_media"
    __table_args__ = (
        UniqueConstraint("product_id", "display_order", name="uq_product_media_product_order"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    product: Mapped[Product] = relationship(back_populates="media")
