"""Initial empty migration.

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-27 00:00:00.000000
"""

from collections.abc import Sequence

revision: str = "0001_initial"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Establish Alembic revision history before domain tables are introduced."""


def downgrade() -> None:
    """Revert the initial empty revision."""
