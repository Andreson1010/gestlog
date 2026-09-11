"""Testes de migração do Alembic."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


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
    assert "alembic_version" in tabelas


def test_downgrade_base_remove_tabelas(alembic_config: tuple[Config, str]) -> None:
    cfg, db_url = alembic_config
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    tabelas = set(inspect(create_engine(db_url)).get_table_names())
    assert "empresa" not in tabelas
