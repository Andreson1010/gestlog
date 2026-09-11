"""Fábrica de engine e sessão do SQLAlchemy."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
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
