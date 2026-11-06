"""Testes da seleção de empresa ativa para usuários com múltiplos vínculos."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi_users.password import PasswordHelper
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession as AsyncSessao

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
async def motor_async(tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    banco = tmp_path / "ativa.db"
    motor = build_async_engine(
        Settings(_env_file=None, database_url=f"sqlite+aiosqlite:///{banco}")
    )
    await init_async_db(motor)
    yield motor
    await motor.dispose()


@pytest.fixture
async def app(motor_async: AsyncEngine) -> AsyncIterator[FastAPI]:
    aplicacao = create_app(_settings())

    async def _override_session() -> AsyncIterator[AsyncSessao]:
        factory = build_async_session_factory(motor_async)
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


async def _usuario_com_duas_empresas(motor: AsyncEngine) -> None:
    """Cria um usuário admin em duas empresas (A criada antes de B)."""
    factory = build_async_session_factory(motor)
    async with factory() as session:
        usuario = User(
            email="multi@empresa.com",
            hashed_password=PasswordHelper().hash(_SENHA),
            is_active=True,
            is_verified=True,
        )
        a = Empresa(nome="Empresa A")
        b = Empresa(nome="Empresa B")
        session.add_all([usuario, a, b])
        await session.flush()
        session.add_all(
            [
                Membership(user_id=usuario.id, empresa_id=a.id, papel="admin"),
                Membership(user_id=usuario.id, empresa_id=b.id, papel="operador"),
            ]
        )
        await session.commit()


async def _login(client: AsyncClient) -> None:
    resposta = await client.post(
        "/auth/login", data={"username": "multi@empresa.com", "password": _SENHA}
    )
    assert resposta.status_code == 204, resposta.text


async def _id_da_empresa_b(motor: AsyncEngine) -> str:
    factory = build_async_session_factory(motor)
    async with factory() as session:
        empresa_b = (
            await session.execute(select(Empresa).where(Empresa.nome == "Empresa B"))
        ).scalar_one()
        return str(empresa_b.id)


async def test_sem_cookie_usa_vinculo_mais_antigo(
    client: AsyncClient, motor_async: AsyncEngine
) -> None:
    await _usuario_com_duas_empresas(motor_async)
    await _login(client)

    resposta = await client.get("/")

    assert resposta.status_code == 200
    assert "<strong>Empresa A</strong>" in resposta.text


async def test_troca_empresa_ativa_pelo_seletor(
    client: AsyncClient, motor_async: AsyncEngine
) -> None:
    await _usuario_com_duas_empresas(motor_async)
    await _login(client)
    alvo = await _id_da_empresa_b(motor_async)

    troca = await client.post("/empresa/ativa", data={"empresa_id": alvo})
    home = await client.get("/")

    assert troca.status_code == 303
    assert home.status_code == 200
    assert "<strong>Empresa B</strong>" in home.text


async def test_troca_sem_vinculo_e_negada(
    client: AsyncClient, motor_async: AsyncEngine
) -> None:
    await _usuario_com_duas_empresas(motor_async)
    await _login(client)

    resposta = await client.post("/empresa/ativa", data={"empresa_id": str(uuid4())})

    assert resposta.status_code == 403


async def test_troca_com_empresa_id_invalido_e_recusada(
    client: AsyncClient, motor_async: AsyncEngine
) -> None:
    await _usuario_com_duas_empresas(motor_async)
    await _login(client)

    resposta = await client.post("/empresa/ativa", data={"empresa_id": "nao-e-uuid"})

    assert resposta.status_code == 400


async def test_cookie_malformado_cai_no_vinculo_mais_antigo(
    client: AsyncClient, motor_async: AsyncEngine
) -> None:
    await _usuario_com_duas_empresas(motor_async)
    await _login(client)
    client.cookies.set("gestlog_empresa_ativa", "nao-e-um-uuid")

    resposta = await client.get("/")

    assert resposta.status_code == 200
    assert "<strong>Empresa A</strong>" in resposta.text
