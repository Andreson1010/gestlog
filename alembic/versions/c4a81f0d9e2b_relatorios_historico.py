"""relatorios historico

Revision ID: c4a81f0d9e2b
Revises: 9c2f7a41b6d3
Create Date: 2026-09-28 10:00:00.000000

"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = 'c4a81f0d9e2b'
down_revision: Union[str, Sequence[str], None] = '9c2f7a41b6d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_sql() -> str:
    """Expressão SQL que gera o id do snapshot, portável entre dialetos."""
    if op.get_bind().dialect.name == "postgresql":
        return "gen_random_uuid()"
    return "lower(hex(randomblob(16)))"


def upgrade() -> None:
    """Adiciona colunas, cria o histórico versionado e faz o backfill."""
    op.add_column(
        'stock_item',
        sa.Column('categoria', sa.String(length=60), nullable=False, server_default=''),
    )
    op.add_column(
        'transport_record',
        sa.Column('previsao_entrega', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'transport_record',
        sa.Column('data_entrega', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        'catalogo_historico',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('empresa_id', sa.Uuid(), nullable=False),
        sa.Column('dominio', sa.String(length=20), nullable=False),
        sa.Column('chave', sa.String(length=80), nullable=False),
        sa.Column('import_job_id', sa.Uuid(), nullable=True),
        sa.Column('importado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('nome', sa.String(length=120), nullable=True),
        sa.Column('categoria', sa.String(length=60), nullable=True),
        sa.Column('local', sa.String(length=40), nullable=True),
        sa.Column('quantidade', sa.Integer(), nullable=True),
        sa.Column('minimo', sa.Integer(), nullable=True),
        sa.Column('prazo_dias', sa.Integer(), nullable=True),
        sa.Column('avaliacao', sa.Float(), nullable=True),
        sa.Column('ativo', sa.Boolean(), nullable=True),
        sa.Column('origem', sa.String(length=80), nullable=True),
        sa.Column('destino', sa.String(length=80), nullable=True),
        sa.Column('peso_kg', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=120), nullable=True),
        sa.Column('previsao_entrega', sa.DateTime(timezone=True), nullable=True),
        sa.Column('data_entrega', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresa.id'], ),
        sa.ForeignKeyConstraint(['import_job_id'], ['import_job.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_catalogo_historico_empresa_dominio_em'),
        'catalogo_historico',
        ['empresa_id', 'dominio', 'importado_em'],
        unique=False,
    )
    op.create_index(
        op.f('ix_catalogo_historico_empresa_dominio_chave'),
        'catalogo_historico',
        ['empresa_id', 'dominio', 'chave', 'importado_em'],
        unique=False,
    )
    _backfill()


def _backfill() -> None:
    """Insere um snapshot por linha existente dos catálogos (job nulo)."""
    uid = _uuid_sql()
    agora = datetime.now(UTC)
    op.execute(
        sa.text(
            f"INSERT INTO catalogo_historico (id, empresa_id, dominio, chave, "
            f"import_job_id, importado_em, nome, categoria, local, quantidade, minimo) "
            f"SELECT {uid}, empresa_id, 'estoque', upper(sku), NULL, :agora, "
            f"nome, categoria, local, quantidade, minimo FROM stock_item"
        ).bindparams(agora=agora)
    )
    op.execute(
        sa.text(
            f"INSERT INTO catalogo_historico (id, empresa_id, dominio, chave, "
            f"import_job_id, importado_em, nome, categoria, prazo_dias, "
            f"avaliacao, ativo) "
            f"SELECT {uid}, empresa_id, 'fornecedores', upper(fornecedor_id), NULL, "
            f":agora, nome, categoria, prazo_dias, avaliacao, ativo FROM supplier"
        ).bindparams(agora=agora)
    )
    op.execute(
        sa.text(
            f"INSERT INTO catalogo_historico (id, empresa_id, dominio, chave, "
            f"import_job_id, importado_em, origem, destino, peso_kg, status, "
            f"previsao_entrega, data_entrega) "
            f"SELECT {uid}, empresa_id, 'transporte', upper(codigo_rastreio), NULL, "
            f":agora, origem, destino, peso_kg, status, previsao_entrega, "
            f"data_entrega FROM transport_record"
        ).bindparams(agora=agora)
    )


def downgrade() -> None:
    """Remove a tabela, os índices e as colunas adicionadas."""
    op.drop_index(
        op.f('ix_catalogo_historico_empresa_dominio_chave'),
        table_name='catalogo_historico',
    )
    op.drop_index(
        op.f('ix_catalogo_historico_empresa_dominio_em'),
        table_name='catalogo_historico',
    )
    op.drop_table('catalogo_historico')
    op.drop_column('transport_record', 'data_entrega')
    op.drop_column('transport_record', 'previsao_entrega')
    op.drop_column('stock_item', 'categoria')
