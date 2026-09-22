"""Testes de integração da página pública de cadastro."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from fastapi_users.password import PasswordHelper
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
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

_CONTA = {
    "nome_empresa": "Transportes Nova",
    "email": "nova@empresa.com",
    "senha": "senha-boa-123",
}


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


async def _login(client: AsyncClient, email: str, senha: str = _SENHA) -> None:
    resposta = await client.post(
        "/auth/login", data={"username": email, "password": senha}
    )
    assert resposta.status_code == 204
    assert client.cookies.get(_COOKIE)


async def _contar(engine: AsyncEngine, modelo: type) -> int:
    factory = build_async_session_factory(engine)
    async with factory() as session:
        return int(
            (
                await session.execute(select(func.count()).select_from(modelo))
            ).scalar_one()
        )


async def test_cadastro_renderiza_formulario(client: AsyncClient) -> None:
    resposta = await client.get("/cadastro")

    assert resposta.status_code == 200
    assert 'name="nome_empresa"' in resposta.text
    assert 'name="email"' in resposta.text
    assert 'name="senha"' in resposta.text
    assert 'href="/login"' in resposta.text


async def test_cadastro_com_sessao_redireciona_para_home(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    await _criar_usuario_com_empresa(engine, "a@empresa.com")
    await _login(client, "a@empresa.com")

    resposta = await client.get("/cadastro", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/"


async def test_cadastro_cria_conta_e_permite_login(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    resposta = await client.post("/cadastro", data=_CONTA, follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login"
    assert await _contar(engine, Empresa) == 1
    assert await _contar(engine, Membership) == 1

    await _login(client, _CONTA["email"], _CONTA["senha"])


async def test_cadastro_email_duplicado_nao_cria_outra_empresa(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    await _criar_usuario_com_empresa(engine, _CONTA["email"])

    resposta = await client.post("/cadastro", data=_CONTA)

    assert resposta.status_code == 400
    assert "já cadastrado" in resposta.text
    assert await _contar(engine, Empresa) == 1


async def test_cadastro_senha_curta_recusa(client: AsyncClient) -> None:
    resposta = await client.post("/cadastro", data={**_CONTA, "senha": "curta"})

    assert resposta.status_code == 400
    assert 'name="nome_empresa"' in resposta.text


async def test_cadastro_email_invalido_recusa(client: AsyncClient) -> None:
    resposta = await client.post("/cadastro", data={**_CONTA, "email": "invalido"})

    assert resposta.status_code == 400
    assert 'name="nome_empresa"' in resposta.text


async def test_cadastro_nome_empresa_vazio_recusa(client: AsyncClient) -> None:
    resposta = await client.post("/cadastro", data={**_CONTA, "nome_empresa": "   "})

    assert resposta.status_code == 400
    assert 'name="nome_empresa"' in resposta.text


async def test_cadastro_corrida_de_email_retorna_409(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy.exc import IntegrityError

    import gestlog.web.app as app_module

    async def _colidir(*args: object, **kwargs: object) -> None:
        raise IntegrityError("insert", {}, Exception("duplicado"))

    monkeypatch.setattr(app_module, "criar_conta", _colidir)

    resposta = await client.post("/cadastro", data=_CONTA)

    assert resposta.status_code == 409
    assert "já cadastrado" in resposta.text


@pytest.mark.parametrize(
    "nome_empresa",
    ["", "x" * 121],
)
async def test_cadastro_nome_empresa_invalido_recusa(
    client: AsyncClient, nome_empresa: str
) -> None:
    resposta = await client.post(
        "/cadastro", data={**_CONTA, "nome_empresa": nome_empresa}
    )

    assert resposta.status_code == 400
    assert 'name="nome_empresa"' in resposta.text
