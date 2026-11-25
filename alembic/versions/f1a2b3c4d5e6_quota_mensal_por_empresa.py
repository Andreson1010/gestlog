"""quota mensal de tokens por empresa

Revision ID: f1a2b3c4d5e6
Revises: e8a1c5d9f3b7
Create Date: 2026-11-25 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e8a1c5d9f3b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Adiciona a quota própria da empresa; NULL herda o teto global do Settings."""
    op.add_column(
        "empresa",
        sa.Column("token_quota_mensal", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Remove a coluna de quota por empresa."""
    op.drop_column("empresa", "token_quota_mensal")
