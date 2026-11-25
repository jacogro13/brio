"""add language preference to users

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Per-user UI + assistant language. Existing rows adopt 'en'; the
    # server_default keeps future inserts valid without an app-side value.
    op.add_column(
        "users",
        sa.Column("language", sa.String(), nullable=False, server_default="en"),
    )


def downgrade() -> None:
    op.drop_column("users", "language")
