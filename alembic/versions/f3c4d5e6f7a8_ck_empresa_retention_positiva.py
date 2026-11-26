"""constraint de retenção positiva na empresa

Revision ID: f3c4d5e6f7a8
Revises: f2b3c4d5e6f7
Create Date: 2026-11-25 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "f3c4d5e6f7a8"
down_revision: str | Sequence[str] | None = "f2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT = "ck_empresa_retention_positiva"
_CONDICAO = "retention_days IS NULL OR retention_days >= 1"


def upgrade() -> None:
    """Exige prazo de retenção positivo (ou nulo) na tabela empresa.

    ``batch_alter_table`` recria a tabela no SQLite (que não aceita
    ``ADD CONSTRAINT``) e segue o caminho nativo no Postgres; nos dois casos
    valores legados inválidos falham a migração (fail-closed).
    """
    with op.batch_alter_table("empresa") as batch:
        batch.create_check_constraint(_CONSTRAINT, _CONDICAO)


def downgrade() -> None:
    """Remove a constraint de retenção positiva."""
    with op.batch_alter_table("empresa") as batch:
        batch.drop_constraint(_CONSTRAINT, type_="check")
