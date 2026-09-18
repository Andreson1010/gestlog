"""Testes de integração do dashboard de KPIs (KPI-01)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi_users.password import PasswordHelper
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import Session, sessionmaker

from gestlog.auth import get_async_session
from gestlog.config import Settings, get_settings
from gestlog.db.models import (
    Conversation,
    Empresa,
    Feedback,
    Membership,
    Message,
    Recommendation,
    StockItem,
    Supplier,
    TransportRecord,
    User,
)
from gestlog.db.session import (
    build_async_engine,
    build_async_session_factory,
    build_engine,
    build_session_factory,
    init_async_db,
)
from gestlog.repositories.kpis import KpiRepository
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
    banco = tmp_path / "kpis.db"
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


@pytest.fixture
def fabrica_sync(engines: tuple[AsyncEngine, Engine]) -> sessionmaker[Session]:
    _, motor_sync = engines
    return build_session_factory(motor_sync)


async def _criar_usuario_com_empresa(
    motor_async: AsyncEngine, email: str, papel: str = "admin"
) -> Empresa:
    factory = build_async_session_factory(motor_async)
    async with factory() as session:
        empresa = Empresa(nome=f"Empresa {email}")
        usuario = User(
            email=email,
            hashed_password=PasswordHelper().hash(_SENHA),
            is_active=True,
            is_verified=True,
        )
        session.add_all([empresa, usuario])
        await session.flush()
        session.add(Membership(user_id=usuario.id, empresa_id=empresa.id, papel=papel))
        await session.commit()
        return empresa


async def _login(client: AsyncClient, email: str) -> None:
    resposta = await client.post(
        "/auth/login", data={"username": email, "password": _SENHA}
    )
    assert resposta.status_code == 204
    assert client.cookies.get(_COOKIE)


def _semear(
    session: Session,
    empresa_id: UUID,
    quando: datetime,
    decisoes: tuple[str, ...] = ("aceita",),
    quando_recomendacao: datetime | None = None,
) -> None:
    """Cria conversa, mensagens, recomendação e decisões para o período.

    ``quando_recomendacao`` permite descolar a recomendação do início da
    conversa, para testar o recorte de período das decisões vigentes.
    """
    conversa = Conversation(empresa_id=empresa_id, user_id=uuid4(), created_at=quando)
    session.add(conversa)
    session.flush()
    session.add_all(
        [
            Message(
                conversation_id=conversa.id,
                papel="user",
                conteudo_redigido="pergunta",
                created_at=quando,
            ),
            Message(
                conversation_id=conversa.id,
                papel="assistant",
                conteudo_redigido="resposta",
                created_at=quando,
            ),
        ]
    )
    recomendacao = Recommendation(
        conversation_id=conversa.id,
        dominio="estoque",
        texto="repor",
        created_at=quando_recomendacao or quando,
    )
    session.add(recomendacao)
    session.flush()
    for indice, decisao in enumerate(decisoes):
        session.add(
            Feedback(
                recommendation_id=recomendacao.id,
                decisao=decisao,
                user_id=uuid4(),
                created_at=recomendacao.created_at + timedelta(seconds=indice),
            )
        )


def test_kpi_repository_agrega_e_isola(fabrica_sync: sessionmaker[Session]) -> None:
    empresa_a, empresa_b = uuid4(), uuid4()
    quando = datetime(2026, 6, 10, 12, tzinfo=UTC)
    with fabrica_sync() as session:
        _semear(session, empresa_a, quando, decisoes=("aceita", "descartada"))
        _semear(session, empresa_a, quando, decisoes=("aceita",))
        _semear(session, empresa_b, quando, decisoes=("descartada",))
        session.add_all(
            [
                StockItem(empresa_id=empresa_a, sku="S1", nome="Caixa"),
                StockItem(empresa_id=empresa_a, sku="S2", nome="Fita"),
                Supplier(empresa_id=empresa_a, fornecedor_id="F1", nome="Forn"),
                TransportRecord(
                    empresa_id=empresa_a, codigo_rastreio="R1", status="ok"
                ),
            ]
        )
        session.commit()

        resumo_a = KpiRepository(session).resumo(empresa_a)
        resumo_b = KpiRepository(session).resumo(empresa_b)

    assert resumo_a.conversas == 2
    assert resumo_a.perguntas == 2
    assert resumo_a.recomendacoes == 2
    assert resumo_a.aceitas == 1
    assert resumo_a.descartadas == 1
    assert resumo_a.taxa_aceitacao == 0.5
    assert resumo_a.cobertura_dados == 4
    assert resumo_b.conversas == 1
    assert resumo_b.aceitas == 0
    assert resumo_b.descartadas == 1


def test_kpi_repository_filtra_por_periodo(
    fabrica_sync: sessionmaker[Session],
) -> None:
    empresa = uuid4()
    janeiro = datetime(2026, 1, 10, 12, tzinfo=UTC)
    junho = datetime(2026, 6, 10, 12, tzinfo=UTC)
    with fabrica_sync() as session:
        _semear(session, empresa, janeiro)
        _semear(session, empresa, junho)
        session.commit()

        repo = KpiRepository(session)
        total = repo.resumo(empresa)
        filtrado = repo.resumo(
            empresa,
            desde=datetime(2026, 6, 1, tzinfo=UTC),
            ate=datetime(2026, 6, 30, tzinfo=UTC),
        )

    assert total.conversas == 2
    assert filtrado.conversas == 1
    assert filtrado.perguntas == 1


def test_kpi_repository_ultima_decisao_vence(
    fabrica_sync: sessionmaker[Session],
) -> None:
    empresa = uuid4()
    quando = datetime(2026, 6, 10, 12, tzinfo=UTC)
    with fabrica_sync() as session:
        _semear(session, empresa, quando, decisoes=("aceita", "descartada"))
        session.commit()
        resumo = KpiRepository(session).resumo(empresa)

    assert resumo.aceitas == 0
    assert resumo.descartadas == 1
    assert resumo.taxa_aceitacao == 0.0


def test_kpi_repository_decisao_respeita_periodo_da_conversa(
    fabrica_sync: sessionmaker[Session],
) -> None:
    empresa = uuid4()
    janeiro = datetime(2026, 1, 10, 12, tzinfo=UTC)
    junho = datetime(2026, 6, 10, 12, tzinfo=UTC)
    with fabrica_sync() as session:
        _semear(session, empresa, janeiro, ("aceita",), quando_recomendacao=junho)
        session.commit()

        filtrado = KpiRepository(session).resumo(
            empresa,
            desde=datetime(2026, 6, 1, tzinfo=UTC),
            ate=datetime(2026, 6, 30, tzinfo=UTC),
        )

    assert filtrado.recomendacoes == 0
    assert filtrado.aceitas == 0
    assert filtrado.decisoes == 0


async def test_kpis_sem_sessao_retorna_401(client: AsyncClient) -> None:
    assert (await client.get("/kpis")).status_code == 401


async def test_kpis_operador_recebe_403(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "op@empresa.com", papel="operador")
    await _login(client, "op@empresa.com")

    assert (await client.get("/kpis")).status_code == 403


async def test_pagina_kpis_renderiza_indicadores(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa = await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    quando = datetime(2026, 6, 10, 12, tzinfo=UTC)
    with fabrica_sync() as session:
        _semear(session, empresa.id, quando, ("aceita",))
        _semear(session, empresa.id, quando, ("descartada",))
        session.commit()

    await _login(client, "a@empresa.com")
    resposta = await client.get("/kpis")

    assert resposta.status_code == 200
    assert "Indicadores" in resposta.text
    assert "Aceitação" in resposta.text
    assert "50%" in resposta.text
    assert "Cobertura de dados" in resposta.text
    assert 'name="desde"' in resposta.text


async def test_pagina_kpis_filtra_periodo(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa = await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    with fabrica_sync() as session:
        _semear(session, empresa.id, datetime(2026, 1, 10, tzinfo=UTC), ("aceita",))
        _semear(session, empresa.id, datetime(2026, 6, 10, tzinfo=UTC), ("descartada",))
        session.commit()

    await _login(client, "a@empresa.com")
    resposta = await client.get(
        "/kpis", params={"desde": "2026-06-01", "ate": "2026-06-30"}
    )

    assert resposta.status_code == 200
    assert "0%" in resposta.text
