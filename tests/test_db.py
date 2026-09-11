"""Testes da camada de banco de dados (modelos e sessão)."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from gestlog.config import Settings
from gestlog.db import build_engine, build_session_factory, init_db, models
from gestlog.db.base import Base


@pytest.fixture
def engine() -> Engine:
    settings = Settings(_env_file=None, database_url="sqlite+pysqlite:///:memory:")
    resolved = build_engine(settings)
    init_db(resolved)
    return resolved


@pytest.fixture
def session(engine: Engine) -> Session:
    factory = build_session_factory(engine)
    with factory() as sessao:
        yield sessao


def test_sqlite_memoria_usa_static_pool() -> None:
    settings = Settings(_env_file=None, database_url="sqlite+pysqlite:///:memory:")
    assert isinstance(build_engine(settings).pool, StaticPool)


def test_tabelas_criadas(engine: Engine) -> None:
    esperadas = {
        "tenant",
        "user",
        "membership",
        "import_job",
        "import_error",
        "stock_item",
        "supplier",
        "transport_record",
        "conversation",
        "message",
        "recommendation",
        "feedback",
        "usage_record",
        "audit_log",
    }
    assert esperadas <= set(Base.metadata.tables)


def test_user_tem_colunas_do_fastapi_users() -> None:
    colunas = set(models.User.__table__.columns.keys())
    assert {"id", "email", "hashed_password", "is_active", "is_verified"} <= colunas


def test_dados_isolados_por_tenant(session: Session) -> None:
    t1 = models.Tenant(nome="A")
    t2 = models.Tenant(nome="B")
    session.add_all([t1, t2])
    session.commit()
    session.add(
        models.StockItem(tenant_id=t1.id, sku="SKU-1", nome="Caixa", quantidade=10)
    )
    session.commit()

    do_t1 = (
        session.execute(
            select(models.StockItem).where(models.StockItem.tenant_id == t1.id)
        )
        .scalars()
        .all()
    )
    do_t2 = (
        session.execute(
            select(models.StockItem).where(models.StockItem.tenant_id == t2.id)
        )
        .scalars()
        .all()
    )
    assert len(do_t1) == 1
    assert do_t2 == []


def test_sku_unico_por_tenant(session: Session) -> None:
    t = models.Tenant(nome="A")
    session.add(t)
    session.commit()
    session.add(models.StockItem(tenant_id=t.id, sku="SKU-1", nome="a"))
    session.commit()
    session.add(models.StockItem(tenant_id=t.id, sku="SKU-1", nome="b"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_import_job_com_erros(session: Session) -> None:
    t = models.Tenant(nome="A")
    session.add(t)
    session.commit()
    job = models.ImportJob(tenant_id=t.id, tipo="estoque")
    job.errors.append(models.ImportError(linha=2, motivo="sku ausente"))
    session.add(job)
    session.commit()
    assert len(job.errors) == 1
    assert job.errors[0].motivo == "sku ausente"
