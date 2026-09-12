"""Dependências de banco assíncrono para o FastAPI Users.

A camada de autenticação usa ``AsyncSession`` (exigência do FastAPI Users 15),
enquanto o restante do sistema permanece síncrono. Ver AD-012 no STATE.md.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from gestlog.config import get_settings
from gestlog.db.models import User
from gestlog.db.session import build_async_engine, build_async_session_factory


@lru_cache(maxsize=1)
def get_async_engine() -> AsyncEngine:
    """Retorna (e memoiza) o engine assíncrono do processo."""
    return build_async_engine(get_settings())


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """Fornece uma sessão assíncrona por requisição."""
    factory = build_async_session_factory(get_async_engine())
    async with factory() as session:
        yield session


async def get_user_db(
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> AsyncIterator[SQLAlchemyUserDatabase]:
    """Fornece o adaptador de usuários do FastAPI Users."""
    yield SQLAlchemyUserDatabase(session, User)
