"""Testes de integração da fila de correções e da decisão (T10)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi_users.password import PasswordHelper
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import Session, sessionmaker

from gestlog.auth import get_async_session
from gestlog.config import Settings, get_settings
from gestlog.correcoes import CorrectionService
from gestlog.db.models import Empresa, ItemCorrecao, Membership, StockItem, User
from gestlog.db.session import (
    build_async_engine,
    build_async_session_factory,
    build_engine,
    build_session_factory,
    init_async_db,
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
    banco = tmp_path / "correcoes.db"
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


async def _criar_empresa_usuario(
    motor_async: AsyncEngine, email: str, papel: str = "admin"
) -> tuple[Empresa, User]:
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
        return empresa, usuario


async def _login(client: AsyncClient, email: str) -> None:
    resposta = await client.post(
        "/auth/login", data={"username": email, "password": _SENHA}
    )
    assert resposta.status_code == 204
    assert client.cookies.get(_COOKIE)


def _semear_base(session: Session, empresa_id: UUID) -> None:
    """Cria um item completo que serve de base para a sugestão de ``local``."""
    session.add(
        StockItem(
            empresa_id=empresa_id,
            sku="BASE",
            nome="Fita",
            quantidade=10,
            minimo=2,
            local="A1",
        )
    )
    session.commit()


def _semear_incompletos(
    session: Session, empresa_id: UUID, quantidade: int = 1, sku_prefixo: str = "S"
) -> None:
    """Cria ``quantidade`` itens de estoque sem ``local``."""
    for indice in range(1, quantidade + 1):
        session.add(
            StockItem(
                empresa_id=empresa_id,
                sku=f"{sku_prefixo}{indice}",
                nome=f"Item {indice}",
                quantidade=1,
                minimo=5,
                local="",
            )
        )
    session.commit()


def _item_pendente(
    fabrica: sessionmaker[Session], empresa_id: UUID, sku: str = "S1"
) -> ItemCorrecao:
    with fabrica() as session:
        stmt = select(ItemCorrecao).where(
            ItemCorrecao.empresa_id == empresa_id,
            ItemCorrecao.alvo_chave == sku,
        )
        item = session.execute(stmt).scalar_one()
        session.expunge(item)
        return item


async def _gerar_fila(fabrica: sessionmaker[Session], empresa_id: UUID) -> None:
    with fabrica() as session:
        CorrectionService(session, empresa_id).gerar_fila()


async def test_sem_sessao_recebe_401(client: AsyncClient) -> None:
    assert (await client.get("/correcoes")).status_code == 401


async def test_operador_recebe_403(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_empresa_usuario(motor_async, "op@empresa.com", papel="operador")
    await _login(client, "op@empresa.com")

    assert (await client.get("/correcoes")).status_code == 403


async def test_gestor_acessa_fila(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_empresa_usuario(motor_async, "gestor@empresa.com", papel="gestor")
    await _login(client, "gestor@empresa.com")

    assert (await client.get("/correcoes")).status_code == 200


async def test_fila_lista_pendentes_do_tenant(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa, _ = await _criar_empresa_usuario(motor_async, "a@empresa.com")
    with fabrica_sync() as session:
        _semear_base(session, empresa.id)
        _semear_incompletos(session, empresa.id)

    await _login(client, "a@empresa.com")
    resposta = await client.get("/correcoes")

    assert resposta.status_code == 200
    assert "S1" in resposta.text
    assert "A1" in resposta.text
    assert 'aria-label="Aprovar' in resposta.text
    assert 'action="/correcoes/' in resposta.text


async def test_fila_isola_outro_tenant(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa_a, _ = await _criar_empresa_usuario(motor_async, "a@empresa.com")
    empresa_b, _ = await _criar_empresa_usuario(motor_async, "b@empresa.com")
    with fabrica_sync() as session:
        _semear_base(session, empresa_a.id)
        _semear_incompletos(session, empresa_a.id)
        _semear_base(session, empresa_b.id)
        _semear_incompletos(session, empresa_b.id, sku_prefixo="B")

    await _login(client, "a@empresa.com")
    resposta = await client.get("/correcoes")

    assert resposta.status_code == 200
    assert "S1" in resposta.text
    assert "B1" not in resposta.text


async def test_fila_sem_dados_orienta_importar(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_empresa_usuario(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    resposta = await client.get("/correcoes")

    assert resposta.status_code == 200
    assert "Sem dados importados" in resposta.text
    assert 'href="/importar"' in resposta.text


async def test_fila_vazia_com_cadastros_completos(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa, _ = await _criar_empresa_usuario(motor_async, "a@empresa.com")
    with fabrica_sync() as session:
        _semear_base(session, empresa.id)

    await _login(client, "a@empresa.com")
    resposta = await client.get("/correcoes")

    assert resposta.status_code == 200
    assert "Nenhuma correção pendente" in resposta.text


async def test_item_sem_sugestao_nao_permite_aprovar(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa, _ = await _criar_empresa_usuario(motor_async, "a@empresa.com")
    with fabrica_sync() as session:
        _semear_incompletos(session, empresa.id)

    await _login(client, "a@empresa.com")
    resposta = await client.get("/correcoes")

    assert resposta.status_code == 200
    assert "sem sugestão" in resposta.text
    assert 'aria-label="Aprovar' not in resposta.text


async def test_limite_invalido_recebe_422(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_empresa_usuario(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    assert (await client.get("/correcoes", params={"limite": 0})).status_code == 422
    assert (await client.get("/correcoes", params={"limite": 999})).status_code == 422


async def test_limite_restringe_listagem(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa, _ = await _criar_empresa_usuario(motor_async, "a@empresa.com")
    with fabrica_sync() as session:
        _semear_base(session, empresa.id)
        _semear_incompletos(session, empresa.id, quantidade=3)

    await _login(client, "a@empresa.com")
    completo = await client.get("/correcoes", params={"limite": 3})
    limitado = await client.get("/correcoes", params={"limite": 1})

    assert completo.text.count('aria-label="Aprovar') == 3
    assert limitado.text.count('aria-label="Aprovar') == 1


async def test_aprovar_redireciona_aplica_e_sai_da_fila(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa, _ = await _criar_empresa_usuario(motor_async, "a@empresa.com")
    with fabrica_sync() as session:
        _semear_base(session, empresa.id)
        _semear_incompletos(session, empresa.id)

    await _login(client, "a@empresa.com")
    await client.get("/correcoes")
    item = _item_pendente(fabrica_sync, empresa.id)

    resposta = await client.post(
        f"/correcoes/{item.id}/decisao",
        data={"decisao": "aprovar"},
        follow_redirects=False,
    )

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/correcoes"
    with fabrica_sync() as session:
        corrigido = session.execute(
            select(StockItem).where(
                StockItem.empresa_id == empresa.id, StockItem.sku == "S1"
            )
        ).scalar_one()
        assert corrigido.local == "A1"

    fila = await client.get("/correcoes")
    assert "Nenhuma correção pendente" in fila.text


async def test_aprovar_sem_sugestao_recebe_409(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa, _ = await _criar_empresa_usuario(motor_async, "a@empresa.com")
    with fabrica_sync() as session:
        _semear_incompletos(session, empresa.id)

    await _login(client, "a@empresa.com")
    await client.get("/correcoes")
    item = _item_pendente(fabrica_sync, empresa.id)

    resposta = await client.post(
        f"/correcoes/{item.id}/decisao", data={"decisao": "aprovar"}
    )

    assert resposta.status_code == 409


async def test_rejeitar_sem_justificativa_recebe_422(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa, _ = await _criar_empresa_usuario(motor_async, "a@empresa.com")
    with fabrica_sync() as session:
        _semear_base(session, empresa.id)
        _semear_incompletos(session, empresa.id)

    await _login(client, "a@empresa.com")
    await client.get("/correcoes")
    item = _item_pendente(fabrica_sync, empresa.id)

    resposta = await client.post(
        f"/correcoes/{item.id}/decisao",
        data={"decisao": "rejeitar", "justificativa": "   "},
    )

    assert resposta.status_code == 422
    assert _item_pendente(fabrica_sync, empresa.id).status == "pendente"


async def test_rejeitar_com_justificativa_encerra_item(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa, _ = await _criar_empresa_usuario(motor_async, "a@empresa.com")
    with fabrica_sync() as session:
        _semear_base(session, empresa.id)
        _semear_incompletos(session, empresa.id)

    await _login(client, "a@empresa.com")
    await client.get("/correcoes")
    item = _item_pendente(fabrica_sync, empresa.id)

    resposta = await client.post(
        f"/correcoes/{item.id}/decisao",
        data={"decisao": "rejeitar", "justificativa": "local incorreto"},
        follow_redirects=False,
    )

    assert resposta.status_code == 303
    rejeitado = _item_pendente(fabrica_sync, empresa.id)
    assert rejeitado.status == "rejeitado"
    assert rejeitado.motivo_rejeicao == "local incorreto"


async def test_decisao_invalida_recebe_422(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa, _ = await _criar_empresa_usuario(motor_async, "a@empresa.com")
    with fabrica_sync() as session:
        _semear_base(session, empresa.id)
        _semear_incompletos(session, empresa.id)

    await _login(client, "a@empresa.com")
    await client.get("/correcoes")
    item = _item_pendente(fabrica_sync, empresa.id)

    resposta = await client.post(
        f"/correcoes/{item.id}/decisao", data={"decisao": "talvez"}
    )

    assert resposta.status_code == 422
    assert _item_pendente(fabrica_sync, empresa.id).status == "pendente"


async def test_decidir_item_de_outro_tenant_recebe_404(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    await _criar_empresa_usuario(motor_async, "a@empresa.com")
    empresa_b, _ = await _criar_empresa_usuario(motor_async, "b@empresa.com")
    with fabrica_sync() as session:
        _semear_base(session, empresa_b.id)
        _semear_incompletos(session, empresa_b.id)
    await _gerar_fila(fabrica_sync, empresa_b.id)
    item_b = _item_pendente(fabrica_sync, empresa_b.id)

    await _login(client, "a@empresa.com")
    resposta = await client.post(
        f"/correcoes/{item_b.id}/decisao", data={"decisao": "aprovar"}
    )

    assert resposta.status_code == 404


async def test_nav_mostra_correcoes_para_gestor(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_empresa_usuario(motor_async, "gestor@empresa.com", papel="gestor")
    await _login(client, "gestor@empresa.com")

    resposta = await client.get("/")

    assert resposta.status_code == 200
    assert 'href="/correcoes"' in resposta.text


async def test_nav_esconde_correcoes_para_operador(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_empresa_usuario(motor_async, "op@empresa.com", papel="operador")
    await _login(client, "op@empresa.com")

    resposta = await client.get("/")

    assert resposta.status_code == 200
    assert 'href="/correcoes"' not in resposta.text
