"""tabela de convites por token

Revision ID: e8a1c5d9f3b7
Revises: d5e6f8a2b7c4
Create Date: 2026-10-28 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8a1c5d9f3b7"
down_revision: str | Sequence[str] | None = "d5e6f8a2b7c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Cria a tabela ``convite`` (AD-015)."""
    op.create_table(
        "convite",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("empresa_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("papel", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresa.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )


def downgrade() -> None:
    """Remove a tabela ``convite``."""
    op.drop_table("convite")
