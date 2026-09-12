"""Testes de integração da autenticação (login/logout por cookie)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from fastapi_users.password import PasswordHelper
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from gestlog.auth import create_auth_router, get_async_engine, get_async_session
from gestlog.config import Settings, get_settings
from gestlog.db.models import User
from gestlog.db.session import (
    build_async_engine,
    build_async_session_factory,
    init_async_db,
)

_SENHA = "senha-secreta-123"
_EMAIL = "operador@empresa.com"
_COOKIE = "gestlog_auth"


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="sqlite+aiosqlite:///:memory:",
        auth_secret="segredo-de-teste-com-pelo-menos-32-bytes",
        auth_cookie_secure=False,
    )


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    motor = build_async_engine(_settings())
    await init_async_db(motor)
    yield motor
    await motor.dispose()


@pytest.fixture
async def app(engine: AsyncEngine) -> AsyncIterator[FastAPI]:
    aplicacao = FastAPI()
    aplicacao.include_router(create_auth_router(_settings()), prefix="/auth")

    async def _override_session() -> AsyncIterator[AsyncSession]:
        factory = build_async_session_factory(engine)
        async with factory() as session:
            yield session

    aplicacao.dependency_overrides[get_async_session] = _override_session
    aplicacao.dependency_overrides[get_settings] = _settings
    yield aplicacao


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as cliente:
        yield cliente


async def _criar_usuario(engine: AsyncEngine, ativo: bool = True) -> None:
    factory = build_async_session_factory(engine)
    async with factory() as session:
        session.add(
            User(
                email=_EMAIL,
                hashed_password=PasswordHelper().hash(_SENHA),
                is_active=ativo,
                is_verified=True,
            )
        )
        await session.commit()


async def test_login_com_credenciais_validas(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    await _criar_usuario(engine)

    resposta = await client.post(
        "/auth/login", data={"username": _EMAIL, "password": _SENHA}
    )

    assert resposta.status_code == 204
    assert client.cookies.get(_COOKIE)


async def test_login_com_senha_invalida(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    await _criar_usuario(engine)

    resposta = await client.post(
        "/auth/login", data={"username": _EMAIL, "password": "errada"}
    )

    assert resposta.status_code == 400
    assert resposta.json()["detail"] == "LOGIN_BAD_CREDENTIALS"


async def test_login_de_usuario_inativo_e_negado(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    await _criar_usuario(engine, ativo=False)

    resposta = await client.post(
        "/auth/login", data={"username": _EMAIL, "password": _SENHA}
    )

    assert resposta.status_code == 400
    assert resposta.json()["detail"] == "LOGIN_BAD_CREDENTIALS"


async def test_logout_sem_sessao_retorna_401(client: AsyncClient) -> None:
    resposta = await client.post("/auth/logout")

    assert resposta.status_code == 401


async def test_logout_encerra_a_sessao(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    await _criar_usuario(engine)
    login = await client.post(
        "/auth/login", data={"username": _EMAIL, "password": _SENHA}
    )
    assert login.status_code == 204
    assert client.cookies.get(_COOKIE)

    saida = await client.post("/auth/logout")

    assert saida.status_code == 204
    assert not client.cookies.get(_COOKIE)


async def test_get_async_session_fornece_sessao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    get_settings.cache_clear()
    get_async_engine.cache_clear()
    try:
        gerador = get_async_session()
        sessao = await anext(gerador)
        assert isinstance(sessao, AsyncSession)
        await gerador.aclose()
    finally:
        await get_async_engine().dispose()
        get_async_engine.cache_clear()
        get_settings.cache_clear()
