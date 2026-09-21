"""Testes de integração do endpoint SSE de chat (T18)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi_users.password import PasswordHelper
from httpx import ASGITransport, AsyncClient
from langchain_core.language_models.chat_models import BaseChatModel
from langgraph.errors import GraphRecursionError
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import Session

from gestlog.auth import get_async_session
from gestlog.config import Settings, get_settings
from gestlog.copilot.service import (
    MENSAGEM_ERRO_COPILOTO,
    MENSAGEM_FORA_DE_ESCOPO,
    CopilotService,
)
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
    banco = tmp_path / "chat.db"
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


def test_get_chat_model_constroi_modelo() -> None:
    get_chat_model.cache_clear()

    assert isinstance(get_chat_model(), BaseChatModel)


async def test_chat_stream_sem_sessao_retorna_401(client: AsyncClient) -> None:
    resposta = await client.get("/chat/stream", params={"pergunta": "oi"})

    assert resposta.status_code == 401


async def test_chat_stream_emite_resposta_sse(
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

    resposta = await client.get(
        "/chat/stream", params={"pergunta": "como está o estoque?"}
    )

    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/event-stream")
    assert "event: resposta" in resposta.text
    assert "Há estoque suficiente" in resposta.text
    assert "Fontes: estoque" in resposta.text
    assert "event: fim" in resposta.text


async def test_chat_stream_fora_de_escopo(
    client: AsyncClient,
    app: FastAPI,
    engines: tuple[AsyncEngine, Engine],
    fake_model_cls: type,
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")
    app.dependency_overrides[get_chat_model] = lambda: fake_model_cls(routes=["FINISH"])

    resposta = await client.get(
        "/chat/stream", params={"pergunta": "qual a capital da França?"}
    )

    assert resposta.status_code == 200
    assert MENSAGEM_FORA_DE_ESCOPO in resposta.text


async def test_chat_stream_pergunta_vazia_retorna_422(
    client: AsyncClient,
    app: FastAPI,
    engines: tuple[AsyncEngine, Engine],
    fake_model_cls: type,
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")
    app.dependency_overrides[get_chat_model] = lambda: fake_model_cls()

    resposta = await client.get("/chat/stream", params={"pergunta": ""})

    assert resposta.status_code == 422


async def test_chat_stream_falha_do_grafo_responde_amigavel(
    client: AsyncClient,
    app: FastAPI,
    engines: tuple[AsyncEngine, Engine],
    fake_model_cls: type,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")
    app.dependency_overrides[get_chat_model] = lambda: fake_model_cls()

    def _explode(self: CopilotService, pergunta: str) -> str:
        raise GraphRecursionError("recursion limit reached")

    monkeypatch.setattr(CopilotService, "answer", _explode)

    resposta = await client.get("/chat/stream", params={"pergunta": "oi"})

    assert resposta.status_code == 200
    assert MENSAGEM_ERRO_COPILOTO in resposta.text
    assert "event: fim" in resposta.text
