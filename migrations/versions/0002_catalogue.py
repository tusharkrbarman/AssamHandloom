"""Create catalogue persistence tables.

Revision ID: 0002_catalogue
Revises: 0001_initial
Create Date: 2026-07-27 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_catalogue"
down_revision: str | Sequence[str] | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

publication_states = "publication_state IN ('draft', 'preview', 'published')"


def _timestamp_columns() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    """Create Phase 1 catalogue tables with PostgreSQL-enforced invariants."""

    op.create_table(
        "artisan_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("biography", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=160), nullable=True),
        sa.Column("portrait_url", sa.String(length=500), nullable=True),
        sa.Column("is_sample", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        *_timestamp_columns(),
    )
    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("silk_type", sa.String(length=80), nullable=False),
        sa.Column("colour", sa.String(length=80), nullable=True),
        sa.Column("occasion", sa.String(length=80), nullable=True),
        sa.Column("artisan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("publication_state", sa.String(length=9), server_default="draft", nullable=False),
        sa.Column("featured_rank", sa.Integer(), server_default="0", nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint(publication_states, name="ck_products_publication_state"),
        sa.ForeignKeyConstraint(["artisan_id"], ["artisan_profiles.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("slug", name="uq_products_slug"),
    )
    op.create_table(
        "variants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=True),
        sa.Column("price_minor", sa.Integer(), nullable=False),
        sa.Column("compare_at_price_minor", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), server_default="INR", nullable=False),
        sa.Column("weight_grams", sa.Integer(), nullable=True),
        sa.Column("inventory_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("publication_state", sa.String(length=9), server_default="draft", nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint(publication_states, name="ck_variants_publication_state"),
        sa.CheckConstraint("price_minor >= 0", name="ck_variants_price_minor_non_negative"),
        sa.CheckConstraint(
            "compare_at_price_minor IS NULL OR compare_at_price_minor >= price_minor",
            name="ck_variants_compare_at_price_not_less_than_price",
        ),
        sa.CheckConstraint(
            "weight_grams IS NULL OR weight_grams >= 0", name="ck_variants_weight_non_negative"
        ),
        sa.CheckConstraint("inventory_quantity >= 0", name="ck_variants_inventory_non_negative"),
        sa.CheckConstraint(
            "currency ~ '^[A-Z]{3}$'",
            name="ck_variants_currency_uppercase_format",
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("sku", name="uq_variants_sku"),
    )
    op.create_table(
        "collections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("publication_state", sa.String(length=9), server_default="draft", nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        *_timestamp_columns(),
        sa.CheckConstraint(publication_states, name="ck_collections_publication_state"),
        sa.UniqueConstraint("slug", name="uq_collections_slug"),
    )
    op.create_table(
        "collection_products",
        sa.Column("collection_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["collection_id"], ["collections.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("collection_id", "product_id"),
        sa.UniqueConstraint(
            "collection_id", "display_order", name="uq_collection_products_collection_order"
        ),
    )
    op.create_table(
        "product_media",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("alt_text", sa.String(length=255), nullable=True),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        *_timestamp_columns(),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("product_id", "display_order", name="uq_product_media_product_order"),
    )
    op.create_index("ix_products_catalogue_filters", "products", ["publication_state", "silk_type"])
    op.create_index(
        "ix_variants_product_publication", "variants", ["product_id", "publication_state"]
    )


def downgrade() -> None:
    """Remove catalogue persistence tables in dependency order."""

    op.drop_index("ix_variants_product_publication", table_name="variants")
    op.drop_index("ix_products_catalogue_filters", table_name="products")
    op.drop_table("product_media")
    op.drop_table("collection_products")
    op.drop_table("collections")
    op.drop_table("variants")
    op.drop_table("products")
    op.drop_table("artisan_profiles")
