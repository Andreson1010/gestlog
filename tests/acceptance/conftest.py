"""Fixtures compartilhadas dos testes de aceitação da F2 (HITL)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import Session, sessionmaker

from gestlog.auth import get_async_session
from gestlog.config import Settings, get_settings
from gestlog.db.session import (
    build_async_engine,
    build_async_session_factory,
    build_engine,
    build_session_factory,
    init_async_db,
)
from gestlog.web import create_app, get_sync_session


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="sqlite+aiosqlite:///:memory:",
        auth_secret="segredo-de-teste-com-pelo-menos-32-bytes",
        auth_cookie_secure=False,
    )


@pytest.fixture
async def motores(tmp_path: Path) -> AsyncIterator[tuple[AsyncEngine, Engine]]:
    banco = tmp_path / "f2.db"
    motor_async = build_async_engine(
        Settings(_env_file=None, database_url=f"sqlite+aiosqlite:///{banco}")
    )
    await init_async_db(motor_async)
    motor_sync = build_engine(
        Settings(_env_file=None, database_url=f"sqlite+pysqlite:///{banco}")
    )
    yield motor_async, motor_sync
    await motor_async.dispose()
    motor_sync.dispose()


@pytest.fixture
def fabrica_sync(motores: tuple[AsyncEngine, Engine]) -> sessionmaker[Session]:
    _, motor_sync = motores
    return build_session_factory(motor_sync)


@pytest.fixture
async def app(motores: tuple[AsyncEngine, Engine]) -> AsyncIterator[FastAPI]:
    motor_async, motor_sync = motores
    aplicacao = create_app(_settings())

    async def _override_async_session() -> AsyncIterator[AsyncSession]:
        factory = build_async_session_factory(motor_async)
        async with factory() as session:
            yield session

    def _override_sync_session() -> Iterator[Session]:
        factory = build_session_factory(motor_sync)
        with factory() as session:
            yield session

    aplicacao.dependency_overrides[get_async_session] = _override_async_session
    aplicacao.dependency_overrides[get_sync_session] = _override_sync_session
    aplicacao.dependency_overrides[get_settings] = _settings
    yield aplicacao


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as cliente:
        yield cliente
