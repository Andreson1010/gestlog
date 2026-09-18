"""Fábrica de engine e sessão do SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from gestlog.config import Settings, get_settings
from gestlog.db.base import Base


def build_engine(settings: Settings | None = None) -> Engine:
    """Cria o engine a partir da ``database_url``.

    Para SQLite em memória usa ``StaticPool`` e desativa a checagem de thread,
    permitindo compartilhar a mesma conexão entre testes.
    """
    resolved = settings or get_settings()
    url = resolved.database_url
    if url.startswith("sqlite") and ":memory:" in url:
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(url)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Cria a fábrica de sessões ligada ao ``engine``."""
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def init_db(engine: Engine) -> None:
    """Cria todas as tabelas registradas na ``Base``."""
    from gestlog.db import models  # noqa: F401

    Base.metadata.create_all(engine)


def build_async_engine(settings: Settings | None = None) -> AsyncEngine:
    """Cria o engine assíncrono a partir da ``database_url``.

    Usado pela camada de autenticação (FastAPI Users). Para SQLite em memória
    usa ``StaticPool`` para compartilhar a mesma conexão.
    """
    resolved = settings or get_settings()
    url = resolved.database_url
    if url.startswith("sqlite") and ":memory:" in url:
        return create_async_engine(
            url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_async_engine(url)


def build_async_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Cria a fábrica de sessões assíncronas ligada ao ``engine``."""
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def init_async_db(engine: AsyncEngine) -> None:
    """Cria todas as tabelas registradas na ``Base`` (engine assíncrono)."""
    from gestlog.db import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
