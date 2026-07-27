"""Persist sample collection ownership and canonical collection keys.

Revision ID: 0005_sample_collection_ownership
Revises: 0004_canonical_catalogue_keys
Create Date: 2026-07-27 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_sample_collection_ownership"
down_revision: str | Sequence[str] | None = "0004_canonical_catalogue_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add explicit collection ownership and prevent case-only slug collisions."""

    duplicates = op.get_bind().execute(
        sa.text(
            "SELECT lower(slug) AS canonical_value FROM collections GROUP BY lower(slug) "
            "HAVING count(*) > 1 ORDER BY canonical_value LIMIT 10"
        )
    ).scalars().all()
    if duplicates:
        values = ", ".join(str(value) for value in duplicates)
        raise RuntimeError(
            "Cannot create canonical collection-slug index because pre-existing case-only "
            f"duplicates were found (collection slugs canonical values: {values}). Resolve or "
            "rename the duplicate live collections, then rerun this migration; no records were "
            "merged or deleted."
        )
    op.add_column(
        "collections",
        sa.Column("is_sample", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index(
        "uq_collections_slug_canonical", "collections", [sa.text("lower(slug)")], unique=True
    )


def downgrade() -> None:
    """Remove collection sample ownership and canonical key protection."""

    op.drop_index("uq_collections_slug_canonical", table_name="collections")
    op.drop_column("collections", "is_sample")
