"""Testes de integração da UI de upload e histórico de importação (T13)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

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
from gestlog.repositories.catalog import StockRepository
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
    banco = tmp_path / "test.db"
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


def _csv(texto: str) -> bytes:
    return texto.encode("utf-8")


async def test_pagina_importar_sem_sessao_redireciona_ao_login(
    client: AsyncClient,
) -> None:
    resposta = await client.get("/importar", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/login"


async def test_pagina_importar_renderiza_formulario(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    resposta = await client.get("/importar")

    assert resposta.status_code == 200
    assert 'name="tipo"' in resposta.text
    assert 'name="arquivo"' in resposta.text
    assert "estoque" in resposta.text
    assert "data-dropzone" in resposta.text
    assert "data-nome-arquivo" in resposta.text
    assert 'class="sr-only"' in resposta.text


async def test_upload_valido_reflete_status_e_grava_dados(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, motor_sync = engines
    empresa = await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    resposta = await client.post(
        "/importar",
        data={"tipo": "estoque"},
        files={
            "arquivo": (
                "estoque.csv",
                _csv("sku,nome,quantidade,minimo\nSKU-1,Caixa,10,2\n"),
                "text/csv",
            )
        },
    )

    assert resposta.status_code == 200
    assert "estoque" in resposta.text
    assert "1 aceitas" in resposta.text
    assert "0 rejeitadas" in resposta.text
    assert 'class="status-card status-ok"' in resposta.text
    with Session(motor_sync) as session:
        assert StockRepository(session).get_by_sku(empresa.id, "SKU-1") is not None


async def test_upload_com_linha_invalida_reporta_erro_por_linha(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    resposta = await client.post(
        "/importar",
        data={"tipo": "estoque"},
        files={
            "arquivo": (
                "estoque.csv",
                _csv("sku,nome,quantidade,minimo\nSKU-1,Caixa,10,2\n,Caixa,3,1\n"),
                "text/csv",
            )
        },
    )

    assert resposta.status_code == 200
    assert "1 aceitas" in resposta.text
    assert "1 rejeitadas" in resposta.text
    assert "Linha 3" in resposta.text
    assert "sku" in resposta.text


async def test_upload_arquivo_invalido_nao_grava(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    resposta = await client.post(
        "/importar",
        data={"tipo": "inexistente"},
        files={"arquivo": ("dados.csv", _csv("a\n1\n"), "text/csv")},
    )

    assert resposta.status_code == 200
    assert "desconhecido" in resposta.text
    assert 'class="status-card status-erro"' in resposta.text


async def test_historico_lista_importacoes_da_empresa(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    await client.post(
        "/importar",
        data={"tipo": "estoque"},
        files={
            "arquivo": (
                "estoque.csv",
                _csv("sku,nome,quantidade,minimo\nSKU-1,Caixa,10,2\n"),
                "text/csv",
            )
        },
    )

    resposta = await client.get("/importar/historico")

    assert resposta.status_code == 200
    assert "estoque" in resposta.text
    assert "concluido" in resposta.text
    assert "1" in resposta.text


async def test_historico_vazio_orienta_a_importar(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    resposta = await client.get("/importar/historico")

    assert resposta.status_code == 200
    assert "Nenhuma importação" in resposta.text


async def test_historico_isola_por_empresa(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _criar_usuario_com_empresa(motor_async, "b@empresa.com")

    await _login(client, "a@empresa.com")
    await client.post(
        "/importar",
        data={"tipo": "estoque"},
        files={
            "arquivo": (
                "estoque.csv",
                _csv("sku,nome,quantidade,minimo\nSKU-1,Caixa,10,2\n"),
                "text/csv",
            )
        },
    )
    await client.post("/auth/logout")

    await _login(client, "b@empresa.com")
    resposta = await client.get("/importar/historico")

    assert resposta.status_code == 200
    assert "Nenhuma importação" in resposta.text
