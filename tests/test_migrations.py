"""Testes de migração do Alembic."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


@pytest.fixture
def alembic_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Config, str]:
    db_url = f"sqlite+pysqlite:///{tmp_path / 'mig.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "alembic")
    return cfg, db_url


def test_upgrade_head_cria_tabelas(alembic_config: tuple[Config, str]) -> None:
    cfg, db_url = alembic_config
    command.upgrade(cfg, "head")

    tabelas = set(inspect(create_engine(db_url)).get_table_names())
    assert {"empresa", "user", "stock_item", "audit_log"} <= tabelas
    assert "item_correcao" in tabelas
    assert "alembic_version" in tabelas


def test_item_correcao_tem_indices(alembic_config: tuple[Config, str]) -> None:
    cfg, db_url = alembic_config
    command.upgrade(cfg, "head")

    inspetor = inspect(create_engine(db_url))
    indices = {indice["name"] for indice in inspetor.get_indexes("item_correcao")}
    assert {"ix_item_correcao_empresa_status", "ix_item_correcao_alvo"} <= indices


def test_upgrade_head_cria_colunas_e_historico(
    alembic_config: tuple[Config, str],
) -> None:
    cfg, db_url = alembic_config
    command.upgrade(cfg, "head")

    inspetor = inspect(create_engine(db_url))
    assert "catalogo_historico" in inspetor.get_table_names()
    colunas_estoque = {coluna["name"] for coluna in inspetor.get_columns("stock_item")}
    colunas_transporte = {
        coluna["name"] for coluna in inspetor.get_columns("transport_record")
    }
    assert "categoria" in colunas_estoque
    assert {"previsao_entrega", "data_entrega"} <= colunas_transporte


def test_catalogo_historico_tem_indices(alembic_config: tuple[Config, str]) -> None:
    cfg, db_url = alembic_config
    command.upgrade(cfg, "head")

    inspetor = inspect(create_engine(db_url))
    indices = {indice["name"] for indice in inspetor.get_indexes("catalogo_historico")}
    assert {
        "ix_catalogo_historico_empresa_dominio_em",
        "ix_catalogo_historico_empresa_dominio_chave",
    } <= indices


def test_downgrade_remove_historico_e_colunas(
    alembic_config: tuple[Config, str],
) -> None:
    cfg, db_url = alembic_config
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "9c2f7a41b6d3")

    inspetor = inspect(create_engine(db_url))
    assert "catalogo_historico" not in inspetor.get_table_names()
    assert "categoria" not in {
        col["name"] for col in inspetor.get_columns("stock_item")
    }
    assert "previsao_entrega" not in {
        col["name"] for col in inspetor.get_columns("transport_record")
    }


def test_backfill_historico_dos_catalogos(alembic_config: tuple[Config, str]) -> None:
    cfg, db_url = alembic_config
    command.upgrade(cfg, "9c2f7a41b6d3")
    engine = create_engine(db_url)
    empresa_id = uuid4().hex
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO empresa (id, nome, retention_days, created_at) "
                "VALUES (:id, 'A', NULL, CURRENT_TIMESTAMP)"
            ),
            {"id": empresa_id},
        )
        conn.execute(
            text(
                "INSERT INTO stock_item "
                "(id, empresa_id, sku, nome, quantidade, minimo, local) "
                "VALUES (:id, :empresa, 'SKU-1', 'Caixa', 5, 1, 'A1')"
            ),
            {"id": uuid4().hex, "empresa": empresa_id},
        )
        conn.execute(
            text(
                "INSERT INTO supplier "
                "(id, empresa_id, fornecedor_id, nome, categoria, prazo_dias, "
                "avaliacao, ativo) "
                "VALUES (:id, :empresa, 'F-1', 'TransLog', 'transporte', 5, 4.5, 1)"
            ),
            {"id": uuid4().hex, "empresa": empresa_id},
        )
        conn.execute(
            text(
                "INSERT INTO transport_record "
                "(id, empresa_id, codigo_rastreio, origem, destino, peso_kg, status) "
                "VALUES (:id, :empresa, 'GL-1', 'SP', 'CWB', 10, 'ok')"
            ),
            {"id": uuid4().hex, "empresa": empresa_id},
        )

    command.upgrade(cfg, "head")

    with engine.connect() as conn:
        total = conn.execute(
            text("SELECT COUNT(*) FROM catalogo_historico")
        ).scalar_one()
        dominios = set(
            conn.execute(text("SELECT dominio FROM catalogo_historico")).scalars()
        )
        jobs_nulos = conn.execute(
            text(
                "SELECT COUNT(*) FROM catalogo_historico " "WHERE import_job_id IS NULL"
            )
        ).scalar_one()
    assert total == 3
    assert dominios == {"estoque", "fornecedores", "transporte"}
    assert jobs_nulos == 3


def test_downgrade_base_remove_tabelas(alembic_config: tuple[Config, str]) -> None:
    cfg, db_url = alembic_config
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    tabelas = set(inspect(create_engine(db_url)).get_table_names())
    assert "empresa" not in tabelas
    assert "item_correcao" not in tabelas
    assert "catalogo_historico" not in tabelas
