"""Enforce canonical catalogue stable-key uniqueness.

Revision ID: 0004_canonical_catalogue_keys
Revises: 0003_sample_catalogue_ownership
Create Date: 2026-07-27 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_canonical_catalogue_keys"
down_revision: str | Sequence[str] | None = "0003_sample_catalogue_ownership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Prevent case-only slug and SKU duplicates at PostgreSQL level."""

    op.create_index("uq_products_slug_canonical", "products", [sa.text("lower(slug)")], unique=True)
    op.create_index("uq_variants_sku_canonical", "variants", [sa.text("upper(sku)")], unique=True)


def downgrade() -> None:
    """Remove canonical stable-key uniqueness indexes."""

    op.drop_index("uq_variants_sku_canonical", table_name="variants")
    op.drop_index("uq_products_slug_canonical", table_name="products")
