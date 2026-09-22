"""Testes de integração da página HTML de administração de usuários (T6)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi_users.password import PasswordHelper
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
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


async def _criar_empresa(engine: AsyncEngine, nome: str) -> Empresa:
    factory = build_async_session_factory(engine)
    async with factory() as session:
        empresa = Empresa(nome=nome)
        session.add(empresa)
        await session.commit()
        return empresa


async def _criar_usuario(
    engine: AsyncEngine, empresa_id: UUID, email: str, papel: str = "operador"
) -> User:
    factory = build_async_session_factory(engine)
    async with factory() as session:
        usuario = User(
            email=email,
            hashed_password=PasswordHelper().hash(_SENHA),
            is_active=True,
            is_verified=True,
        )
        session.add(usuario)
        await session.flush()
        session.add(Membership(user_id=usuario.id, empresa_id=empresa_id, papel=papel))
        await session.commit()
        return usuario


async def _papel_do_usuario(engine: AsyncEngine, usuario_id: UUID) -> str | None:
    factory = build_async_session_factory(engine)
    async with factory() as session:
        vinculo = (
            (
                await session.execute(
                    select(Membership).where(Membership.user_id == usuario_id)
                )
            )
            .scalars()
            .first()
        )
        return None if vinculo is None else vinculo.papel


async def _login(client: AsyncClient, email: str) -> None:
    resposta = await client.post(
        "/auth/login", data={"username": email, "password": _SENHA}
    )
    assert resposta.status_code == 204
    assert client.cookies.get(_COOKIE)


async def test_pagina_lista_usuarios_da_empresa(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    empresa = await _criar_empresa(engine, "A")
    await _criar_usuario(engine, empresa.id, "admin@empresa.com", papel="admin")
    await _criar_usuario(engine, empresa.id, "op@empresa.com")
    outra = await _criar_empresa(engine, "B")
    await _criar_usuario(engine, outra.id, "outro@empresa.com", papel="admin")

    await _login(client, "admin@empresa.com")
    resposta = await client.get("/admin/usuarios")

    assert resposta.status_code == 200
    assert "admin@empresa.com" in resposta.text
    assert "op@empresa.com" in resposta.text
    assert "outro@empresa.com" not in resposta.text
    assert 'href="/admin/usuarios"' in resposta.text


async def test_operador_nao_acessa_admin(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    empresa = await _criar_empresa(engine, "A")
    await _criar_usuario(engine, empresa.id, "op@empresa.com")

    await _login(client, "op@empresa.com")

    assert (await client.get("/admin/usuarios")).status_code == 403


async def test_nav_esconde_usuarios_para_operador(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    empresa = await _criar_empresa(engine, "A")
    await _criar_usuario(engine, empresa.id, "op@empresa.com")

    await _login(client, "op@empresa.com")
    resposta = await client.get("/")

    assert resposta.status_code == 200
    assert 'href="/admin/usuarios"' not in resposta.text


async def test_nav_mostra_usuarios_para_admin(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    empresa = await _criar_empresa(engine, "A")
    await _criar_usuario(engine, empresa.id, "admin@empresa.com", papel="admin")

    await _login(client, "admin@empresa.com")
    resposta = await client.get("/")

    assert resposta.status_code == 200
    assert 'href="/admin/usuarios"' in resposta.text


async def test_admin_altera_papel(client: AsyncClient, engine: AsyncEngine) -> None:
    empresa = await _criar_empresa(engine, "A")
    await _criar_usuario(engine, empresa.id, "admin@empresa.com", papel="admin")
    operador = await _criar_usuario(engine, empresa.id, "op@empresa.com")

    await _login(client, "admin@empresa.com")
    resposta = await client.post(
        f"/admin/usuarios/{operador.id}/papel",
        data={"papel": "gestor"},
        follow_redirects=False,
    )

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/admin/usuarios"
    assert await _papel_do_usuario(engine, operador.id) == "gestor"


async def test_admin_remove_usuario(client: AsyncClient, engine: AsyncEngine) -> None:
    empresa = await _criar_empresa(engine, "A")
    await _criar_usuario(engine, empresa.id, "admin@empresa.com", papel="admin")
    operador = await _criar_usuario(engine, empresa.id, "op@empresa.com")

    await _login(client, "admin@empresa.com")
    resposta = await client.post(
        f"/admin/usuarios/{operador.id}/remover", follow_redirects=False
    )

    assert resposta.status_code == 303
    assert await _papel_do_usuario(engine, operador.id) is None


async def test_papel_invalido_recusa(client: AsyncClient, engine: AsyncEngine) -> None:
    empresa = await _criar_empresa(engine, "A")
    admin = await _criar_usuario(engine, empresa.id, "admin@empresa.com", papel="admin")

    await _login(client, "admin@empresa.com")
    resposta = await client.post(
        f"/admin/usuarios/{admin.id}/papel", data={"papel": "chefe"}
    )

    assert resposta.status_code == 400
    assert await _papel_do_usuario(engine, admin.id) == "admin"


async def test_protege_ultimo_administrador(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    empresa = await _criar_empresa(engine, "A")
    admin = await _criar_usuario(engine, empresa.id, "admin@empresa.com", papel="admin")

    await _login(client, "admin@empresa.com")

    rebaixar = await client.post(
        f"/admin/usuarios/{admin.id}/papel", data={"papel": "gestor"}
    )
    remover = await client.post(f"/admin/usuarios/{admin.id}/remover")

    assert rebaixar.status_code == 409
    assert remover.status_code == 409
    assert await _papel_do_usuario(engine, admin.id) == "admin"


async def test_nao_gerencia_usuario_de_outra_empresa(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    empresa_a = await _criar_empresa(engine, "A")
    empresa_b = await _criar_empresa(engine, "B")
    await _criar_usuario(engine, empresa_a.id, "admin_a@empresa.com", papel="admin")
    outro = await _criar_usuario(
        engine, empresa_b.id, "user_b@empresa.com", papel="admin"
    )

    await _login(client, "admin_a@empresa.com")

    assert (
        await client.post(
            f"/admin/usuarios/{outro.id}/papel", data={"papel": "operador"}
        )
    ).status_code == 404
    assert (await client.post(f"/admin/usuarios/{outro.id}/remover")).status_code == 404
