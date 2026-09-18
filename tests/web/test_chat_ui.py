"""Testes de integração da UI de chat com HTMX/SSE (T19)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi_users.password import PasswordHelper
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import Session

from gestlog.auth import get_async_session
from gestlog.config import Settings, get_settings
from gestlog.db.models import Empresa, Membership, User
from gestlog.db.session import (
    build_async_engine,
    build_async_session_factory,
    build_engine,
    build_session_factory,
    init_async_db,
)
from gestlog.web import create_app, get_chat_model, get_sync_session

_SENHA = "senha-secreta-123"
_COOKIE = "gestlog_auth"


def _tool_comum(resposta: str, fontes: str = "") -> list[dict[str, Any]]:
    return [
        {
            "name": "enviar_resposta_logistica",
            "args": {"resposta": resposta, "fontes": fontes, "justificativa": ""},
            "id": "call-1",
            "type": "tool_call",
        }
    ]


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="sqlite+aiosqlite:///:memory:",
        auth_secret="segredo-de-teste-com-pelo-menos-32-bytes",
        auth_cookie_secure=False,
    )


@pytest.fixture
async def engines(tmp_path: Path) -> AsyncIterator[tuple[AsyncEngine, Engine]]:
    banco = tmp_path / "chat_ui.db"
    url = f"sqlite+aiosqlite:///{banco}"
    motor_async = build_async_engine(Settings(_env_file=None, database_url=url))
    await init_async_db(motor_async)
    motor_sync = build_engine(
        Settings(_env_file=None, database_url=f"sqlite+pysqlite:///{banco}")
    )
    yield motor_async, motor_sync
    await motor_async.dispose()
    motor_sync.dispose()


@pytest.fixture
async def app(engines: tuple[AsyncEngine, Engine]) -> AsyncIterator[FastAPI]:
    motor_async, motor_sync = engines
    aplicacao = create_app(_settings())

    async def _override_async_session() -> AsyncIterator[AsyncSession]:
        factory = build_async_session_factory(motor_async)
        async with factory() as session:
            yield session

    def _override_sync_session() -> AsyncIterator[Session]:
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


async def _criar_usuario_com_empresa(motor_async: AsyncEngine, email: str) -> Empresa:
    factory = build_async_session_factory(motor_async)
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


async def test_pagina_chat_sem_sessao_redireciona_ao_login(
    client: AsyncClient,
) -> None:
    resposta = await client.get("/chat", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login"


async def test_pagina_chat_renderiza_formulario(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    resposta = await client.get("/chat")

    assert resposta.status_code == 200
    assert 'hx-get="/chat/pergunta"' in resposta.text
    assert 'name="pergunta"' in resposta.text
    assert 'id="conversa"' in resposta.text
    assert 'aria-live="polite"' in resposta.text
    assert "htmx-ext-sse" in resposta.text
    assert "/static/app.css" in resposta.text


async def test_turno_sem_sessao_redireciona_ao_login(client: AsyncClient) -> None:
    resposta = await client.get(
        "/chat/pergunta", params={"pergunta": "oi"}, follow_redirects=False
    )

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login"


async def test_turno_abre_assinatura_sse(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    resposta = await client.get(
        "/chat/pergunta", params={"pergunta": "como está o estoque?"}
    )

    assert resposta.status_code == 200
    assert 'sse-connect="/chat/stream?pergunta=' in resposta.text
    assert 'sse-swap="resposta"' in resposta.text
    assert 'hx-swap="textContent"' in resposta.text
    assert 'sse-close="fim"' in resposta.text
    assert "como está o estoque?" in resposta.text


async def test_turno_codifica_pergunta_na_url(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    resposta = await client.get("/chat/pergunta", params={"pergunta": "frete & prazo"})

    assert resposta.status_code == 200
    assert 'sse-connect="/chat/stream?pergunta=frete%20%26%20prazo"' in resposta.text


async def test_turno_pergunta_vazia_retorna_422(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    resposta = await client.get("/chat/pergunta", params={"pergunta": ""})

    assert resposta.status_code == 422


async def test_pagina_chat_exibe_historico_apos_pergunta(
    client: AsyncClient,
    app: FastAPI,
    engines: tuple[AsyncEngine, Engine],
    fake_model_cls: type,
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")
    app.dependency_overrides[get_chat_model] = lambda: fake_model_cls(
        routes=["estoque", "FINISH"],
        tool_calls=[_tool_comum("Há estoque suficiente", fontes="estoque")],
    )

    await client.get("/chat/stream", params={"pergunta": "como está o estoque?"})
    resposta = await client.get("/chat")

    assert resposta.status_code == 200
    assert "como está o estoque?" in resposta.text
    assert "Há estoque suficiente" in resposta.text


async def test_historico_nao_vaza_entre_empresas(
    client: AsyncClient,
    app: FastAPI,
    engines: tuple[AsyncEngine, Engine],
    fake_model_cls: type,
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")
    app.dependency_overrides[get_chat_model] = lambda: fake_model_cls(
        routes=["estoque", "FINISH"],
        tool_calls=[_tool_comum("segredo-da-empresa-A", fontes="estoque")],
    )
    await client.get("/chat/stream", params={"pergunta": "pergunta-secreta-A"})

    await _criar_usuario_com_empresa(motor_async, "b@empresa.com")
    await _login(client, "b@empresa.com")
    resposta = await client.get("/chat")

    assert resposta.status_code == 200
    assert "pergunta-secreta-A" not in resposta.text
    assert "segredo-da-empresa-A" not in resposta.text
