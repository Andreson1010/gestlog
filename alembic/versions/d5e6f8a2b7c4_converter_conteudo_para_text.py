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
_INDICES = (
    ("ix_message_conversa_criado", "message", ("conversation_id", "created_at")),
    (
        "ix_recommendation_conversa_criado",
        "recommendation",
        ("conversation_id", "created_at"),
    ),
)


def upgrade() -> None:
    """Remove o teto de 4000 chars e indexa o histórico por conversa."""
    for nome, tabela, colunas in _INDICES:
        op.create_index(nome, tabela, list(colunas))
    for tabela, coluna in _COLUNAS:
        with op.batch_alter_table(tabela) as batch:
            batch.alter_column(coluna, existing_type=sa.String(4000), type_=sa.Text())


def downgrade() -> None:
    """Restaura String(4000) nas duas colunas e remove os índices."""
    for tabela, coluna in _COLUNAS:
        with op.batch_alter_table(tabela) as batch:
            batch.alter_column(coluna, existing_type=sa.Text(), type_=sa.String(4000))
    for nome, tabela, _colunas in _INDICES:
        op.drop_index(nome, table_name=tabela)
