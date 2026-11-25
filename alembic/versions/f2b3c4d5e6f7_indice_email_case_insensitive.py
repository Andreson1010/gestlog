"""índice único funcional de e-mail case-insensitive

Revision ID: f2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-11-25 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision: str = "f2b3c4d5e6f7"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_INDICE = "uq_user_email_ci"


def _emails_duplicados(conexao: Connection) -> list[str]:
    """E-mails que colidem ao ignorar caixa (resolução manual no ADR da task)."""
    stmt = sa.text(
        'SELECT lower(email) FROM "user" '
        "GROUP BY lower(email) HAVING count(*) > 1"
    )
    return [str(linha[0]) for linha in conexao.execute(stmt)]


def upgrade() -> None:
    """Cria o índice único funcional; aborta listando duplicatas (fail-fast)."""
    conflitos = _emails_duplicados(op.get_bind())
    if conflitos:
        raise RuntimeError(
            "user tem e-mails duplicados (ignorando caixa); resolva manualmente "
            "antes de migrar: " + ", ".join(conflitos)
        )
    op.create_index(_INDICE, "user", [sa.text("lower(email)")], unique=True)


def downgrade() -> None:
    """Remove o índice único funcional de e-mail."""
    op.drop_index(_INDICE, table_name="user")
