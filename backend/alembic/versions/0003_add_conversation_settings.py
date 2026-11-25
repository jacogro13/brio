"""add per-conversation settings

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("temperature", sa.Float(), nullable=True))
    op.add_column("conversations", sa.Column("max_tokens", sa.Integer(), nullable=True))
    op.add_column("conversations", sa.Column("system_prompt_override", sa.String(), nullable=True))
    op.add_column("conversations", sa.Column("enable_thinking", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "enable_thinking")
    op.drop_column("conversations", "system_prompt_override")
    op.drop_column("conversations", "max_tokens")
    op.drop_column("conversations", "temperature")
