"""Testes de integração do onboarding da conta e convites."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from gestlog.auth import (
    create_auth_router,
    get_async_session,
    get_current_empresa,
)
from gestlog.config import Settings, get_settings
from gestlog.db.models import Convite, Empresa
from gestlog.db.session import (
    build_async_engine,
    build_async_session_factory,
    init_async_db,
)
from gestlog.web import create_app, create_onboarding_router
from gestlog.web.rate_limit import limitador

_SENHA = "senha-secreta-123"
_COOKIE = "gestlog_auth"


def _hash_token_sha256(token: str) -> str:
    """SHA-256 hex do token, espelhando o repositório de convites."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _settings_limite_1() -> Settings:
    """Settings com limite de 1 tentativa por janela (roda o 429 cedo)."""
    return Settings(
        _env_file=None,
        database_url="sqlite+aiosqlite:///:memory:",
        auth_secret="segredo-de-teste-com-pelo-menos-32-bytes",
        auth_cookie_secure=False,
        rate_limit_tentativas=1,
        rate_limit_janela_segundos=86_400,
    )


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


@pytest.fixture
async def app_real(engine: AsyncEngine) -> AsyncIterator[FastAPI]:
    """App real (`create_app`) para conferir o wiring do limitador em produção."""
    aplicacao = create_app(_settings())

    async def _override_session() -> AsyncIterator[AsyncSession]:
        factory = build_async_session_factory(engine)
        async with factory() as session:
            yield session

    aplicacao.dependency_overrides[get_async_session] = _override_session
    aplicacao.dependency_overrides[get_settings] = _settings
    yield aplicacao


@pytest.fixture
async def client_real(app_real: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app_real)
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
        json={"email": "operador@empresa.com", "papel": "operador"},
    )
    assert convite.status_code == 201
    token = convite.json()["token"]
    aceite = await client.post(
        "/convites/aceitar", json={"token": token, "senha": _SENHA}
    )
    assert aceite.status_code == 201
    assert aceite.json()["empresa_id"] == dados["empresa_id"]

    await client.post("/auth/logout")
    await _login(client, "operador@empresa.com")
    empresa = await client.get("/empresa")

    assert empresa.status_code == 200
    assert empresa.json()["id"] == dados["empresa_id"]


async def test_convite_exige_papel_admin(client: AsyncClient) -> None:
    await _criar_conta(client)
    await _login(client, "admin@empresa.com")
    convite = await client.post(
        "/empresa/convites",
        json={"email": "operador@empresa.com", "papel": "operador"},
    )
    assert convite.status_code == 201
    aceite = await client.post(
        "/convites/aceitar",
        json={"token": convite.json()["token"], "senha": _SENHA},
    )
    assert aceite.status_code == 201
    await client.post("/auth/logout")
    await _login(client, "operador@empresa.com")

    resposta = await client.post(
        "/empresa/convites",
        json={"email": "outro@empresa.com", "papel": "operador"},
    )

    assert resposta.status_code == 403


async def test_convite_duplicado_retorna_409(client: AsyncClient) -> None:
    await _criar_conta(client)
    await _login(client, "admin@empresa.com")
    corpo = {"email": "operador@empresa.com", "papel": "operador"}

    convite = await client.post("/empresa/convites", json=corpo)
    assert convite.status_code == 201
    aceite = await client.post(
        "/convites/aceitar",
        json={"token": convite.json()["token"], "senha": _SENHA},
    )
    assert aceite.status_code == 201

    duplicado = await client.post("/empresa/convites", json=corpo)

    assert duplicado.status_code == 409


async def test_convite_para_email_registrado_retorna_409(client: AsyncClient) -> None:
    """E-mail registrado (em qualquer empresa) não gera convite (AD-015).

    O token fica em poder do CONVIDADOR, não do convidado: só convites para
    e-mail novo podem ser criados — nunca há redefinição de credencial
    global.
    """
    await _criar_conta(client)
    await _login(client, "admin@empresa.com")

    resposta = await client.post(
        "/empresa/convites",
        json={"email": "admin@empresa.com", "papel": "operador"},
    )

    assert resposta.status_code == 409


async def test_aceite_nao_altera_senha_de_email_registrado(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    """Defense-in-depth: convite forjado para e-mail existente é recusado.

    Mesmo com um convite válido gravado direto no banco (bypass do POST de
    convite, que é barrado), o aceite não altera a senha global e não cria
    vínculo sem consentimento.
    """
    dados = await _criar_conta(client)
    factory = build_async_session_factory(engine)
    async with factory() as session:
        session.add(
            Convite(
                empresa_id=UUID(dados["empresa_id"]),
                email="admin@empresa.com",
                papel="operador",
                token_hash=_hash_token_sha256("token-forjado"),
                expira_em=datetime.now(UTC) + timedelta(days=1),
            )
        )
        await session.commit()

    resposta = await client.post(
        "/convites/aceitar",
        json={"token": "token-forjado", "senha": "senha-do-atacante-123"},
    )
    assert resposta.status_code == 400

    await _login(client, "admin@empresa.com")
    invasao = await client.post(
        "/auth/login",
        data={"username": "admin@empresa.com", "password": "senha-do-atacante-123"},
    )
    assert invasao.status_code in (400, 401)


async def test_convite_invalido_retorna_400(client: AsyncClient) -> None:
    await _criar_conta(client)

    resposta = await client.post(
        "/convites/aceitar", json={"token": "token-inexistente", "senha": _SENHA}
    )

    assert resposta.status_code == 400


async def test_convite_tem_uso_unico(client: AsyncClient) -> None:
    await _criar_conta(client)
    await _login(client, "admin@empresa.com")
    convite = await client.post(
        "/empresa/convites",
        json={"email": "operador@empresa.com", "papel": "operador"},
    )
    assert convite.status_code == 201
    token = convite.json()["token"]
    primeiro = await client.post(
        "/convites/aceitar", json={"token": token, "senha": _SENHA}
    )
    assert primeiro.status_code == 201

    repetido = await client.post(
        "/convites/aceitar", json={"token": token, "senha": _SENHA}
    )

    assert repetido.status_code == 400


async def test_convite_expirado_retorna_400(
    client: AsyncClient,
    engine: AsyncEngine,
) -> None:
    await _criar_conta(client)
    await _login(client, "admin@empresa.com")
    convite = await client.post(
        "/empresa/convites",
        json={"email": "operador@empresa.com", "papel": "operador"},
    )
    assert convite.status_code == 201
    token = convite.json()["token"]
    factory = build_async_session_factory(engine)
    async with factory() as session:
        await session.execute(
            update(Convite)
            .where(Convite.token_hash == _hash_token_sha256(token))
            .values(expira_em=datetime.now(UTC) - timedelta(days=1))
        )
        await session.commit()

    resposta = await client.post(
        "/convites/aceitar", json={"token": token, "senha": _SENHA}
    )

    assert resposta.status_code == 400


async def test_login_limitado_recebe_429_na_rota_real(
    client_real: AsyncClient, app_real: FastAPI
) -> None:
    """O wiring do limitador no router de auth do app real devolve 429."""
    await _criar_conta(client_real)
    app_real.dependency_overrides[get_settings] = _settings_limite_1
    limitador.reset()

    primeira = await client_real.post(
        "/auth/login", data={"username": "admin@empresa.com", "password": _SENHA}
    )
    segunda = await client_real.post(
        "/auth/login", data={"username": "admin@empresa.com", "password": _SENHA}
    )

    assert primeira.status_code == 204
    assert segunda.status_code == 429


async def test_onboarding_limitado_recebe_429_na_rota_real(
    client_real: AsyncClient, app_real: FastAPI
) -> None:
    """O limite vale para a criação de contas pública também."""
    app_real.dependency_overrides[get_settings] = _settings_limite_1
    limitador.reset()
    corpo = {
        "nome_empresa": "Lotus",
        "email": "lotus@empresa.com",
        "senha": _SENHA,
    }

    primeira = await client_real.post("/onboarding", json=corpo)
    segunda = await client_real.post("/onboarding", json=corpo)

    assert primeira.status_code == 201
    assert segunda.status_code == 429


async def test_convites_limitado_recebe_429_na_rota_real(
    client_real: AsyncClient, app_real: FastAPI
) -> None:
    await _criar_conta(client_real)
    await _login(client_real, "admin@empresa.com")
    app_real.dependency_overrides[get_settings] = _settings_limite_1
    limitador.reset()
    corpo = {"email": "operador@empresa.com", "papel": "operador"}

    primeira = await client_real.post("/empresa/convites", json=corpo)
    segunda = await client_real.post("/empresa/convites", json=corpo)

    assert primeira.status_code == 201
    assert segunda.status_code == 429


async def test_aceite_limitado_recebe_429_na_rota_real(
    client_real: AsyncClient, app_real: FastAPI
) -> None:
    app_real.dependency_overrides[get_settings] = _settings_limite_1
    limitador.reset()
    corpo = {"token": "token-inexistente", "senha": _SENHA}

    primeira = await client_real.post("/convites/aceitar", json=corpo)
    segunda = await client_real.post("/convites/aceitar", json=corpo)

    assert primeira.status_code == 400
    assert segunda.status_code == 429
