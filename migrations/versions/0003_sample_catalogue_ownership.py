"""Persist explicit sample-catalogue ownership.

Revision ID: 0003_sample_catalogue_ownership
Revises: 0002_catalogue
Create Date: 2026-07-27 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_sample_catalogue_ownership"
down_revision: str | Sequence[str] | None = "0002_catalogue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add ownership flags without inferring ownership from publication state."""

    op.add_column(
        "products",
        sa.Column("is_sample", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "variants",
        sa.Column("is_sample", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    """Remove explicit sample ownership flags."""

    op.drop_column("variants", "is_sample")
    op.drop_column("products", "is_sample")
