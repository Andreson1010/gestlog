"""item correcao

Revision ID: 9c2f7a41b6d3
Revises: 5f1c4d61cc86
Create Date: 2026-09-22 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9c2f7a41b6d3'
down_revision: Union[str, Sequence[str], None] = '5f1c4d61cc86'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('item_correcao',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('empresa_id', sa.Uuid(), nullable=False),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('alvo_chave', sa.String(length=40), nullable=False),
    sa.Column('campo', sa.String(length=40), nullable=False),
    sa.Column('valor_no_pedido', sa.String(length=255), nullable=False),
    sa.Column('valor_sugerido', sa.String(length=255), nullable=True),
    sa.Column('justificativa', sa.String(length=2000), nullable=False),
    sa.Column('fonte', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('motivo_rejeicao', sa.String(length=2000), nullable=True),
    sa.Column('decidido_por', sa.Uuid(), nullable=True),
    sa.Column('papel_aprovador', sa.String(length=20), nullable=True),
    sa.Column('decidido_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('aplicado_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('motivo_falha', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['empresa_id'], ['empresa.id'], ),
    sa.ForeignKeyConstraint(['decidido_por'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(
        op.f('ix_item_correcao_empresa_status'),
        'item_correcao',
        ['empresa_id', 'status'],
        unique=False,
    )
    op.create_index(
        op.f('ix_item_correcao_alvo'),
        'item_correcao',
        ['empresa_id', 'tipo', 'alvo_chave', 'campo'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_item_correcao_alvo'), table_name='item_correcao')
    op.drop_index(
        op.f('ix_item_correcao_empresa_status'), table_name='item_correcao'
    )
    op.drop_table('item_correcao')
