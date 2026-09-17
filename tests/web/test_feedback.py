"""Testes de integração do endpoint de feedback das recomendações (T22)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi_users.password import PasswordHelper
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import Session

from gestlog.auth import get_async_session
from gestlog.config import Settings, get_settings
from gestlog.db.models import Empresa, Feedback, Membership, User
from gestlog.db.session import (
    build_async_engine,
    build_async_session_factory,
    build_engine,
    build_session_factory,
    init_async_db,
)
from gestlog.repositories.conversations import (
    ConversationRepository,
    FeedbackRepository,
    RecommendationRepository,
)
from gestlog.web import create_app, get_sync_session

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
async def engines(tmp_path: Path) -> AsyncIterator[tuple[AsyncEngine, Engine]]:
    banco = tmp_path / "feedback.db"
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


async def _criar_usuario(
    motor_async: AsyncEngine, email: str, empresa_id: UUID | None = None
) -> tuple[UUID, UUID]:
    factory = build_async_session_factory(motor_async)
    async with factory() as session:
        if empresa_id is None:
            empresa = Empresa(nome="Empresa A")
            session.add(empresa)
            await session.flush()
            empresa_id = empresa.id
        usuario = User(
            email=email,
            hashed_password=PasswordHelper().hash(_SENHA),
            is_active=True,
            is_verified=True,
        )
        session.add(usuario)
        await session.flush()
        session.add(
            Membership(user_id=usuario.id, empresa_id=empresa_id, papel="operador")
        )
        await session.commit()
        return empresa_id, usuario.id


async def _login(client: AsyncClient, email: str) -> None:
    resposta = await client.post(
        "/auth/login", data={"username": email, "password": _SENHA}
    )
    assert resposta.status_code == 204
    assert client.cookies.get(_COOKIE)


def _criar_recomendacao(motor_sync: Engine, empresa_id: UUID, user_id: UUID) -> UUID:
    factory = build_session_factory(motor_sync)
    with factory() as session:
        conversa = ConversationRepository(session).get_or_create(empresa_id, user_id)
        recomendacao = RecommendationRepository(session).add_recommendation(
            conversa.id, "estoque", "Repor SKU-1", "abaixo do mínimo", ["estoque"]
        )
        session.commit()
        return recomendacao.id


def _feedbacks(motor_sync: Engine, recommendation_id: UUID) -> list[Feedback]:
    factory = build_session_factory(motor_sync)
    with factory() as session:
        return FeedbackRepository(session).list_by_recommendation(recommendation_id)


async def test_feedback_sem_sessao_retorna_401(client: AsyncClient) -> None:
    resposta = await client.post(
        f"/recomendacoes/{UUID(int=0)}/feedback", data={"decisao": "aceita"}
    )

    assert resposta.status_code == 401


async def test_registra_aceite_e_descarte(
    client: AsyncClient, app: FastAPI, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, motor_sync = engines
    empresa_id, user_id = await _criar_usuario(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")
    recomendacao_id = _criar_recomendacao(motor_sync, empresa_id, user_id)

    aceite = await client.post(
        f"/recomendacoes/{recomendacao_id}/feedback", data={"decisao": "aceita"}
    )
    descarte = await client.post(
        f"/recomendacoes/{recomendacao_id}/feedback", data={"decisao": "descartada"}
    )

    assert aceite.status_code == 201
    assert aceite.json()["decisao"] == "aceita"
    assert descarte.status_code == 201
    registros = _feedbacks(motor_sync, recomendacao_id)
    assert [registro.decisao for registro in registros] == ["aceita", "descartada"]
    assert {registro.user_id for registro in registros} == {user_id}


async def test_feedback_isola_entre_empresas(
    client: AsyncClient, app: FastAPI, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, motor_sync = engines
    empresa_a, user_a = await _criar_usuario(motor_async, "a@empresa.com")
    recomendacao_id = _criar_recomendacao(motor_sync, empresa_a, user_a)

    await _criar_usuario(motor_async, "b@empresa.com")
    await _login(client, "b@empresa.com")
    resposta = await client.post(
        f"/recomendacoes/{recomendacao_id}/feedback", data={"decisao": "aceita"}
    )

    assert resposta.status_code == 404
    assert _feedbacks(motor_sync, recomendacao_id) == []


async def test_feedback_isola_entre_usuarios_da_empresa(
    client: AsyncClient, app: FastAPI, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, motor_sync = engines
    empresa_a, user_a = await _criar_usuario(motor_async, "a@empresa.com")
    recomendacao_id = _criar_recomendacao(motor_sync, empresa_a, user_a)

    await _criar_usuario(motor_async, "colega@empresa.com", empresa_a)
    await _login(client, "colega@empresa.com")
    resposta = await client.post(
        f"/recomendacoes/{recomendacao_id}/feedback", data={"decisao": "aceita"}
    )

    assert resposta.status_code == 404
    assert _feedbacks(motor_sync, recomendacao_id) == []


async def test_decisao_invalida_retorna_422(
    client: AsyncClient, app: FastAPI, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, motor_sync = engines
    empresa_id, user_id = await _criar_usuario(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")
    recomendacao_id = _criar_recomendacao(motor_sync, empresa_id, user_id)

    resposta = await client.post(
        f"/recomendacoes/{recomendacao_id}/feedback", data={"decisao": "talvez"}
    )

    assert resposta.status_code == 422
    assert _feedbacks(motor_sync, recomendacao_id) == []
