"""alinhar FKs de user ao GUID

Revision ID: b7d2e9a4f108
Revises: c4a81f0d9e2b
Create Date: 2026-10-07 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d2e9a4f108"
down_revision: str | Sequence[str] | None = "c4a81f0d9e2b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUNAS = (
    ("membership", "user_id"),
    ("conversation", "user_id"),
    ("feedback", "user_id"),
    ("audit_log", "user_id"),
    ("item_correcao", "decidido_por"),
)


def _normalizar_legado(tabela: str, coluna: str) -> None:
    """Reformata UUIDs de 32 chars (sem hífen) para 36 chars no SQLite.

    O tipo ``Uuid`` grava ``value.hex`` (32 chars) em backends sem UUID nativo,
    enquanto o ``GUID`` do FastAPI Users grava ``str(value)`` (36 chars, com
    hífens). Sem normalizar, vínculos antigos deixariam de casar com
    ``User.id``. Em backends com UUID nativo (Postgres) não há representação
    textual a corrigir.
    """
    if op.get_bind().dialect.name != "sqlite":
        return
    op.execute(
        sa.text(
            f"UPDATE {tabela} SET {coluna} = "
            f"substr({coluna}, 1, 8) || '-' || substr({coluna}, 9, 4) || '-' || "
            f"substr({coluna}, 13, 4) || '-' || substr({coluna}, 17, 4) || '-' || "
            f"substr({coluna}, 21, 12) "
            f"WHERE length({coluna}) = 32"
        )
    )


def _reverter_legado(tabela: str, coluna: str) -> None:
    """Reverte os UUIDs de 36 chars (com hífen) para 32 chars no SQLite."""
    if op.get_bind().dialect.name != "sqlite":
        return
    op.execute(
        sa.text(
            f"UPDATE {tabela} SET {coluna} = replace({coluna}, '-', '') "
            f"WHERE length({coluna}) = 36"
        )
    )


def upgrade() -> None:
    """Normaliza os UUIDs das FKs de ``user.id`` para o formato do GUID."""
    for tabela, coluna in _COLUNAS:
        _normalizar_legado(tabela, coluna)


def downgrade() -> None:
    """Reverte os UUIDs das FKs de ``user.id`` para o formato do tipo ``Uuid``."""
    for tabela, coluna in _COLUNAS:
        _reverter_legado(tabela, coluna)
