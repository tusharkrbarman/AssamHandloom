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

    duplicates = _canonical_duplicates()
    if duplicates:
        details = "; ".join(
            f"{kind} canonical values: {', '.join(values)}" for kind, values in duplicates
        )
        raise RuntimeError(
            "Cannot create canonical catalogue-key indexes because pre-existing case-only "
            f"duplicates were found ({details}). Resolve or rename the duplicate live catalogue "
            "records, then rerun this migration; no records were merged or deleted."
        )
    op.create_index("uq_products_slug_canonical", "products", [sa.text("lower(slug)")], unique=True)
    op.create_index("uq_variants_sku_canonical", "variants", [sa.text("upper(sku)")], unique=True)


def _canonical_duplicates() -> list[tuple[str, list[str]]]:
    """Return a bounded deterministic diagnostic before mutation or DDL."""

    connection = op.get_bind()
    checks = (
        ("product slugs", "products", "lower(slug)"),
        ("variant SKUs", "variants", "upper(sku)"),
    )
    found: list[tuple[str, list[str]]] = []
    for kind, table, expression in checks:
        rows = connection.execute(
            sa.text(
                f"SELECT {expression} AS canonical_value "
                f"FROM {table} GROUP BY {expression} HAVING count(*) > 1 "
                "ORDER BY canonical_value LIMIT 10"
            )
        ).scalars().all()
        if rows:
            found.append((kind, [str(value) for value in rows]))
    return found


def downgrade() -> None:
    """Remove canonical stable-key uniqueness indexes."""

    op.drop_index("uq_variants_sku_canonical", table_name="variants")
    op.drop_index("uq_products_slug_canonical", table_name="products")
