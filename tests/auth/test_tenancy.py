"""Testes de integração de tenancy: resolução de empresa e guards de acesso."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi_users.password import PasswordHelper
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from gestlog.auth import (
    create_auth_router,
    exigir_papel,
    get_async_session,
    get_current_empresa,
    verificar_empresa_do_recurso,
)
from gestlog.config import Settings, get_settings
from gestlog.db.models import Empresa, Membership, User
from gestlog.db.session import (
    build_async_engine,
    build_async_session_factory,
    init_async_db,
)

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

    @aplicacao.get("/empresa")
    async def empresa_atual(
        empresa: Annotated[Empresa, Depends(get_current_empresa)],
    ) -> dict[str, str]:
        return {"id": str(empresa.id), "nome": empresa.nome}

    @aplicacao.get("/recursos/{empresa_id}")
    async def recurso(
        empresa: Annotated[Empresa, Depends(verificar_empresa_do_recurso)],
    ) -> dict[str, str]:
        return {"empresa": str(empresa.id)}

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


async def _criar_empresa_com_usuario(
    engine: AsyncEngine, nome: str, email: str, papel: str = "operador"
) -> Empresa:
    factory = build_async_session_factory(engine)
    async with factory() as session:
        empresa = Empresa(nome=nome)
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


async def test_sem_sessao_retorna_401(client: AsyncClient) -> None:
    resposta = await client.get("/empresa")

    assert resposta.status_code == 401


async def test_usuario_ve_apenas_a_propria_empresa(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    empresa_a = await _criar_empresa_com_usuario(engine, "A", "a@empresa.com")
    await _criar_empresa_com_usuario(engine, "B", "b@empresa.com")

    await _login(client, "a@empresa.com")
    resposta = await client.get("/empresa")

    assert resposta.status_code == 200
    assert resposta.json() == {"id": str(empresa_a.id), "nome": "A"}


async def test_recurso_de_outra_empresa_retorna_404(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    empresa_a = await _criar_empresa_com_usuario(engine, "A", "a@empresa.com")
    empresa_b = await _criar_empresa_com_usuario(engine, "B", "b@empresa.com")

    await _login(client, "a@empresa.com")

    assert (await client.get(f"/recursos/{empresa_a.id}")).status_code == 200
    assert (await client.get(f"/recursos/{empresa_b.id}")).status_code == 404


async def test_guard_de_papel_nego_operador(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    await _criar_empresa_com_usuario(engine, "A", "admin@empresa.com", papel="admin")
    await _criar_empresa_com_usuario(engine, "B", "op@empresa.com", papel="operador")

    await _login(client, "admin@empresa.com")
    assert (await client.get("/admin")).status_code == 200

    await client.post("/auth/logout")
    await _login(client, "op@empresa.com")
    assert (await client.get("/admin")).status_code == 403


async def test_multiplos_vinculos_resolve_o_mais_antigo(
    client: AsyncClient, engine: AsyncEngine
) -> None:
    primeira = await _criar_empresa_com_usuario(engine, "A", "multi@empresa.com")
    factory = build_async_session_factory(engine)
    async with factory() as session:
        segunda = Empresa(nome="B")
        session.add(segunda)
        await session.flush()
        stmt = select(User).where(User.email == "multi@empresa.com")
        usuario = (await session.execute(stmt)).scalars().first()
        session.add(
            Membership(user_id=usuario.id, empresa_id=segunda.id, papel="operador")
        )
        await session.commit()

    await _login(client, "multi@empresa.com")
    resposta = await client.get("/empresa")

    assert resposta.status_code == 200
    assert resposta.json()["id"] == str(primeira.id)
