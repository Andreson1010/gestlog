"""Testes de integração da home autenticada e do redirecionamento ao login."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from fastapi_users.password import PasswordHelper
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from gestlog.auth import get_async_session
from gestlog.config import Settings, get_settings
from gestlog.db.models import Empresa, Membership, User
from gestlog.db.session import (
    build_async_engine,
    build_async_session_factory,
    init_async_db,
)
from gestlog.web import create_app

_SENHA = "senha-secreta-123"
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
    aplicacao = create_app(_settings())

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


async def _criar_usuario_com_empresa(engine: AsyncEngine, email: str) -> Empresa:
    factory = build_async_session_factory(engine)
    async with factory() as session:
        empresa = Empresa(nome="Empresa A")
        usuario = User(
            email=email,
            hashed_password=PasswordHelper().hash(_SENHA),
            is_active=True,
            is_verified=True,
        )
        session.add_all([empresa, usuario])
        await session.flush()
        session.add(
            Membership(user_id=usuario.id, empresa_id=empresa.id, papel="admin")
        )
        await session.commit()
        return empresa


async def _login(client: AsyncClient, email: str) -> None:
    resposta = await client.post(
        "/auth/login", data={"username": email, "password": _SENHA}
    )
    assert resposta.status_code == 204
    assert client.cookies.get(_COOKIE)


async def test_home_sem_sessao_redireciona_para_login(client: AsyncClient) -> None:
    resposta = await client.get("/", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login"


async def test_login_renderiza_formulario(client: AsyncClient) -> None:
    resposta = await client.get("/login")

    assert resposta.status_code == 200
    assert 'hx-post="/auth/login"' in resposta.text
    assert 'name="password"' in resposta.text


async def test_home_autenticada_renderiza(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    await _criar_usuario_com_empresa(engine, "a@empresa.com")
    await _login(client, "a@empresa.com")

    resposta = await client.get("/")

    assert resposta.status_code == 200
    assert "a@empresa.com" in resposta.text
    assert 'href="/importar"' in resposta.text
    assert 'href="/chat"' in resposta.text


async def test_login_com_sessao_redireciona_para_home(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    await _criar_usuario_com_empresa(engine, "a@empresa.com")
    await _login(client, "a@empresa.com")

    resposta = await client.get("/login", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/"
