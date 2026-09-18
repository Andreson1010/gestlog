"""Testes de integração da gestão de usuários e papéis (ADM-01)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi_users.password import PasswordHelper
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from gestlog.auth import (
    create_auth_router,
    exigir_papel,
    get_async_session,
    get_current_empresa,
)
from gestlog.config import Settings, get_settings
from gestlog.db.models import Empresa, Membership, User
from gestlog.db.session import (
    build_async_engine,
    build_async_session_factory,
    init_async_db,
)
from gestlog.web.admin import create_admin_router

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
    aplicacao.include_router(create_admin_router())

    @aplicacao.get("/empresa")
    async def empresa_atual(
        empresa: Annotated[Empresa, Depends(get_current_empresa)],
    ) -> dict[str, str]:
        return {"id": str(empresa.id)}

    @aplicacao.get("/admin")
    async def admin(
        membership: Annotated[Membership, Depends(exigir_papel("admin"))],
    ) -> dict[str, str]:
        return {"papel": membership.papel}

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


async def _login(client: AsyncClient, email: str) -> None:
    resposta = await client.post(
        "/auth/login", data={"username": email, "password": _SENHA}
    )
    assert resposta.status_code == 204
    assert client.cookies.get(_COOKIE)


async def test_admin_lista_usuarios_da_empresa(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    empresa = await _criar_empresa(engine, "A")
    await _criar_usuario(engine, empresa.id, "admin@empresa.com", papel="admin")
    operador = await _criar_usuario(engine, empresa.id, "op@empresa.com")
    outra = await _criar_empresa(engine, "B")
    await _criar_usuario(engine, outra.id, "outro@empresa.com", papel="admin")

    await _login(client, "admin@empresa.com")
    resposta = await client.get("/empresa/usuarios")

    assert resposta.status_code == 200
    dados = resposta.json()
    assert {item["email"] for item in dados} == {"admin@empresa.com", "op@empresa.com"}
    assert str(operador.id) in {item["usuario_id"] for item in dados}


async def test_operador_nao_gerencia_usuarios(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    empresa = await _criar_empresa(engine, "A")
    operador = await _criar_usuario(engine, empresa.id, "op@empresa.com")
    await _login(client, "op@empresa.com")

    assert (await client.get("/empresa/usuarios")).status_code == 403
    assert (
        await client.patch(f"/empresa/usuarios/{operador.id}", json={"papel": "admin"})
    ).status_code == 403


async def test_admin_altera_papel_e_reflete_permissao(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    empresa = await _criar_empresa(engine, "A")
    await _criar_usuario(engine, empresa.id, "admin@empresa.com", papel="admin")
    operador = await _criar_usuario(engine, empresa.id, "op@empresa.com")

    await _login(client, "op@empresa.com")
    assert (await client.get("/admin")).status_code == 403

    await _login(client, "admin@empresa.com")
    resposta = await client.patch(
        f"/empresa/usuarios/{operador.id}", json={"papel": "admin"}
    )
    assert resposta.status_code == 200
    assert resposta.json()["papel"] == "admin"

    await _login(client, "op@empresa.com")
    assert (await client.get("/admin")).status_code == 200


async def test_admin_remove_usuario_e_revoga_acesso(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    empresa = await _criar_empresa(engine, "A")
    await _criar_usuario(engine, empresa.id, "admin@empresa.com", papel="admin")
    operador = await _criar_usuario(engine, empresa.id, "op@empresa.com")

    await _login(client, "op@empresa.com")
    assert (await client.get("/empresa")).status_code == 200

    await _login(client, "admin@empresa.com")
    assert (await client.delete(f"/empresa/usuarios/{operador.id}")).status_code == 204

    await _login(client, "op@empresa.com")
    assert (await client.get("/empresa")).status_code == 403


async def test_admin_nao_gerencia_usuario_de_outra_empresa(
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
        await client.patch(f"/empresa/usuarios/{outro.id}", json={"papel": "operador"})
    ).status_code == 404
    assert (await client.delete(f"/empresa/usuarios/{outro.id}")).status_code == 404


async def test_alvo_inexistente_retorna_404(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    empresa = await _criar_empresa(engine, "A")
    await _criar_usuario(engine, empresa.id, "admin@empresa.com", papel="admin")
    await _login(client, "admin@empresa.com")
    aleatorio = uuid4()

    assert (
        await client.patch(f"/empresa/usuarios/{aleatorio}", json={"papel": "operador"})
    ).status_code == 404
    assert (await client.delete(f"/empresa/usuarios/{aleatorio}")).status_code == 404


async def test_protege_ultimo_administrador(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    empresa = await _criar_empresa(engine, "A")
    admin = await _criar_usuario(engine, empresa.id, "admin@empresa.com", papel="admin")
    await _login(client, "admin@empresa.com")

    assert (
        await client.patch(f"/empresa/usuarios/{admin.id}", json={"papel": "gestor"})
    ).status_code == 409
    assert (await client.delete(f"/empresa/usuarios/{admin.id}")).status_code == 409
