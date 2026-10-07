"""Testes de migração do Alembic."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect, text


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

    antes = datetime.now(UTC)
    command.upgrade(cfg, "head")
    depois = datetime.now(UTC)

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
        importados_em = (
            conn.execute(text("SELECT importado_em FROM catalogo_historico"))
            .scalars()
            .all()
        )
    assert total == 3
    assert dominios == {"estoque", "fornecedores", "transporte"}
    assert jobs_nulos == 3
    assert len(set(importados_em)) == 1
    gravado = datetime.strptime(importados_em[0], "%Y-%m-%d %H:%M:%S.%f").replace(
        tzinfo=UTC
    )
    assert antes <= gravado <= depois


_FKS_USER = (
    ("membership", "user_id"),
    ("conversation", "user_id"),
    ("feedback", "user_id"),
    ("audit_log", "user_id"),
    ("item_correcao", "decidido_por"),
)


def _linhas_fk_legadas(
    empresa_id: str, legado: str, conversa_id: str, recomendacao_id: str
) -> list[tuple[str, dict[str, str]]]:
    """SQL e bind de uma linha legada por tabela que referencia ``user.id``."""
    return [
        (
            "INSERT INTO membership (id, user_id, empresa_id, papel, created_at) "
            "VALUES (:id, :user, :empresa, 'admin', CURRENT_TIMESTAMP)",
            {"id": uuid4().hex, "user": legado, "empresa": empresa_id},
        ),
        (
            "INSERT INTO conversation (id, empresa_id, user_id, created_at) "
            "VALUES (:id, :empresa, :user, CURRENT_TIMESTAMP)",
            {"id": conversa_id, "empresa": empresa_id, "user": legado},
        ),
        (
            "INSERT INTO recommendation "
            "(id, conversation_id, dominio, texto, justificativa, fontes, created_at) "
            "VALUES (:id, :conversa, 'transporte', 't', 'j', NULL, CURRENT_TIMESTAMP)",
            {"id": recomendacao_id, "conversa": conversa_id},
        ),
        (
            "INSERT INTO feedback "
            "(id, recommendation_id, decisao, user_id, created_at) "
            "VALUES (:id, :rec, 'aceito', :user, CURRENT_TIMESTAMP)",
            {"id": uuid4().hex, "rec": recomendacao_id, "user": legado},
        ),
        (
            "INSERT INTO audit_log "
            "(id, empresa_id, user_id, evento, detalhe, created_at) "
            "VALUES (:id, :empresa, :user, 'evt', NULL, CURRENT_TIMESTAMP)",
            {"id": uuid4().hex, "empresa": empresa_id, "user": legado},
        ),
        (
            "INSERT INTO item_correcao "
            "(id, empresa_id, tipo, alvo_chave, campo, valor_no_pedido, justificativa, "
            "fonte, status, decidido_por, created_at) "
            "VALUES (:id, :empresa, 'estoque', 'SKU-1', 'nome', 'A', 'j', 'manual', "
            "'aprovado', :user, CURRENT_TIMESTAMP)",
            {"id": uuid4().hex, "empresa": empresa_id, "user": legado},
        ),
    ]


def _semear_fk_legadas(engine: Engine, empresa_id: str, usuario_id: str) -> None:
    """Grava empresa, usuário (GUID de 36) e uma FK legada (32) por tabela."""
    legado = usuario_id.replace("-", "")
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
                "INSERT INTO user (id, email, hashed_password, is_active, "
                "is_superuser, is_verified) "
                "VALUES (:id, 'u@a.com', 'x', 1, 0, 1)"
            ),
            {"id": usuario_id},
        )
        linhas = _linhas_fk_legadas(empresa_id, legado, uuid4().hex, uuid4().hex)
        for sql, params in linhas:
            conn.execute(text(sql), params)


def _valor_fk(engine: Engine, tabela: str, coluna: str) -> str:
    """Lê o valor da coluna FK da única linha semeada na tabela."""
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT {coluna} FROM {tabela}")).scalar_one()


def _contagem_join(engine: Engine, tabela: str, coluna: str) -> int:
    """Conta quantas linhas da tabela casam com ``user.id`` por JOIN direto."""
    with engine.connect() as conn:
        return conn.execute(
            text(f"SELECT COUNT(*) FROM {tabela} t JOIN user u ON t.{coluna} = u.id")
        ).scalar_one()


def test_migracao_normaliza_fk_user_para_guid(
    alembic_config: tuple[Config, str],
) -> None:
    cfg, db_url = alembic_config
    command.upgrade(cfg, "c4a81f0d9e2b")
    engine = create_engine(db_url)
    empresa_id = uuid4().hex
    usuario_id = str(uuid4())
    _semear_fk_legadas(engine, empresa_id, usuario_id)
    legado = usuario_id.replace("-", "")

    assert [_valor_fk(engine, t, c) for t, c in _FKS_USER] == [legado] * len(_FKS_USER)
    assert [_contagem_join(engine, t, c) for t, c in _FKS_USER] == [0] * len(_FKS_USER)

    command.upgrade(cfg, "head")

    assert [_valor_fk(engine, t, c) for t, c in _FKS_USER] == [usuario_id] * len(
        _FKS_USER
    )
    assert [_contagem_join(engine, t, c) for t, c in _FKS_USER] == [1] * len(_FKS_USER)

    command.downgrade(cfg, "c4a81f0d9e2b")

    assert [_valor_fk(engine, t, c) for t, c in _FKS_USER] == [legado] * len(_FKS_USER)
    assert [_contagem_join(engine, t, c) for t, c in _FKS_USER] == [0] * len(_FKS_USER)


def test_downgrade_base_remove_tabelas(alembic_config: tuple[Config, str]) -> None:
    cfg, db_url = alembic_config
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    tabelas = set(inspect(create_engine(db_url)).get_table_names())
    assert "empresa" not in tabelas
    assert "item_correcao" not in tabelas
    assert "catalogo_historico" not in tabelas
