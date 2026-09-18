"""Testes de integração do onboarding da conta e convites."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from gestlog.auth import (
    create_auth_router,
    get_async_session,
    get_current_empresa,
)
from gestlog.config import Settings, get_settings
from gestlog.db.models import Empresa
from gestlog.db.session import (
    build_async_engine,
    build_async_session_factory,
    init_async_db,
)
from gestlog.web import create_onboarding_router

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
    aplicacao = FastAPI()
    aplicacao.include_router(create_auth_router(_settings()), prefix="/auth")
    aplicacao.include_router(create_onboarding_router())

    @aplicacao.get("/empresa")
    async def empresa_atual(
        empresa: Annotated[Empresa, Depends(get_current_empresa)],
    ) -> dict[str, str]:
        return {"id": str(empresa.id), "nome": empresa.nome}

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


async def _criar_conta(
    client: AsyncClient, email: str = "admin@empresa.com", nome: str = "Empresa A"
) -> dict[str, str]:
    resposta = await client.post(
        "/onboarding",
        json={"nome_empresa": nome, "email": email, "senha": _SENHA},
    )
    assert resposta.status_code == 201
    return resposta.json()


async def _login(client: AsyncClient, email: str) -> None:
    resposta = await client.post(
        "/auth/login", data={"username": email, "password": _SENHA}
    )
    assert resposta.status_code == 204
    assert client.cookies.get(_COOKIE)


async def test_onboarding_cria_empresa_e_admin(client: AsyncClient) -> None:
    dados = await _criar_conta(client, nome="Logística Alfa")

    await _login(client, "admin@empresa.com")
    empresa = await client.get("/empresa")

    assert empresa.status_code == 200
    assert empresa.json() == {"id": dados["empresa_id"], "nome": "Logística Alfa"}


async def test_onboarding_com_email_repetido_retorna_400(client: AsyncClient) -> None:
    await _criar_conta(client)

    repetido = await client.post(
        "/onboarding",
        json={"nome_empresa": "Outra", "email": "admin@empresa.com", "senha": _SENHA},
    )

    assert repetido.status_code == 400


async def test_admin_convida_usuario_para_a_empresa(client: AsyncClient) -> None:
    dados = await _criar_conta(client)
    await _login(client, "admin@empresa.com")

    convite = await client.post(
        "/empresa/convites",
        json={"email": "operador@empresa.com", "papel": "operador", "senha": _SENHA},
    )
    assert convite.status_code == 201

    await client.post("/auth/logout")
    await _login(client, "operador@empresa.com")
    empresa = await client.get("/empresa")

    assert empresa.status_code == 200
    assert empresa.json()["id"] == dados["empresa_id"]


async def test_convite_exige_papel_admin(client: AsyncClient) -> None:
    await _criar_conta(client)
    await _login(client, "admin@empresa.com")
    await client.post(
        "/empresa/convites",
        json={"email": "operador@empresa.com", "papel": "operador", "senha": _SENHA},
    )
    await client.post("/auth/logout")
    await _login(client, "operador@empresa.com")

    resposta = await client.post(
        "/empresa/convites",
        json={"email": "outro@empresa.com", "papel": "operador", "senha": _SENHA},
    )

    assert resposta.status_code == 403


async def test_convite_duplicado_retorna_409(client: AsyncClient) -> None:
    await _criar_conta(client)
    await _login(client, "admin@empresa.com")
    corpo = {"email": "operador@empresa.com", "papel": "operador", "senha": _SENHA}

    assert (await client.post("/empresa/convites", json=corpo)).status_code == 201
    duplicado = await client.post("/empresa/convites", json=corpo)

    assert duplicado.status_code == 409
