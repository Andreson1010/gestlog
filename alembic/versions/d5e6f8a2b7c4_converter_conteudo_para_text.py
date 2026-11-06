"""converter conteudo_redigido e texto para Text

Revision ID: d5e6f8a2b7c4
Revises: b7d2e9a4f108
Create Date: 2026-10-28 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5e6f8a2b7c4"
down_revision: str | Sequence[str] | None = "b7d2e9a4f108"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUNAS = (
    ("message", "conteudo_redigido"),
    ("recommendation", "texto"),
)


def upgrade() -> None:
    """Remove o teto de 4000 chars do conteudo de message e texto de recommendation."""
    for tabela, coluna in _COLUNAS:
        with op.batch_alter_table(tabela) as batch:
            batch.alter_column(coluna, existing_type=sa.String(4000), type_=sa.Text())


def downgrade() -> None:
    """Restaura String(4000) nas duas colunas."""
    for tabela, coluna in _COLUNAS:
        with op.batch_alter_table(tabela) as batch:
            batch.alter_column(coluna, existing_type=sa.Text(), type_=sa.String(4000))
