"""Testes de integração das rotas de relatórios (REL-25..REL-35)."""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
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
from gestlog.db.models import CatalogoHistorico, Empresa, Membership, User
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
_QUANDO = datetime(2026, 6, 10, 12, tzinfo=UTC)


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="sqlite+aiosqlite:///:memory:",
        auth_secret="segredo-de-teste-com-pelo-menos-32-bytes",
        auth_cookie_secure=False,
    )


@pytest.fixture
async def engines(tmp_path: Path) -> AsyncIterator[tuple[AsyncEngine, Engine]]:
    banco = tmp_path / "relatorios.db"
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


def _snap(
    session: Session,
    empresa_id: UUID,
    dominio: str,
    chave: str,
    **payload: object,
) -> None:
    session.add(
        CatalogoHistorico(
            empresa_id=empresa_id,
            dominio=dominio,
            chave=chave,
            importado_em=_QUANDO,
            **payload,
        )
    )


def _semear_estoque(session: Session, empresa_id: UUID) -> None:
    _snap(
        session,
        empresa_id,
        "estoque",
        "S1",
        nome="Caixa",
        categoria="Embalagem",
        local="A1",
        quantidade=1,
        minimo=5,
    )
    _snap(
        session,
        empresa_id,
        "estoque",
        "S2",
        nome="Pallet",
        categoria="Base",
        local="B1",
        quantidade=30,
        minimo=5,
    )


def _ler_csv(dados: bytes) -> list[list[str]]:
    texto = dados.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(texto), delimiter=";"))


@pytest.mark.parametrize(
    "rota",
    ["/relatorios/estoque", "/relatorios/transporte", "/relatorios/fornecedores"],
)
async def test_relatorios_sem_sessao_401(client: AsyncClient, rota: str) -> None:
    assert (await client.get(rota)).status_code == 401
    assert (await client.get(f"{rota}/exportar")).status_code == 401


async def test_relatorios_operador_recebe_403(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "op@empresa.com", papel="operador")
    await _login(client, "op@empresa.com")

    assert (await client.get("/relatorios/estoque")).status_code == 403
    assert (await client.get("/relatorios/estoque/exportar")).status_code == 403


async def test_relatorios_admin_recebe_200(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    for dominio in ("estoque", "transporte", "fornecedores"):
        assert (await client.get(f"/relatorios/{dominio}")).status_code == 200


async def test_dominio_invalido_404(client: AsyncClient, engines) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    assert (await client.get("/relatorios/financeiro")).status_code == 404
    assert (await client.get("/relatorios/estoque/extra")).status_code == 404


async def test_periodo_invalido_422(client: AsyncClient, engines) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    resposta = await client.get(
        "/relatorios/estoque", params={"desde": "2026-09-30", "ate": "2026-09-01"}
    )

    assert resposta.status_code == 422


async def test_data_invalida_422(client: AsyncClient, engines) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    resposta = await client.get("/relatorios/estoque", params={"desde": "abc"})

    assert resposta.status_code == 422


async def test_pagina_estoque_renderiza_tabelas_e_persiste_periodo(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa = await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    with fabrica_sync() as session:
        _semear_estoque(session, empresa.id)
        session.commit()

    await _login(client, "a@empresa.com")
    resposta = await client.get(
        "/relatorios/estoque", params={"desde": "2026-06-01", "ate": "2026-06-30"}
    )

    assert resposta.status_code == 200
    assert "S1" in resposta.text
    assert "Abaixo do mínimo" in resposta.text
    assert "Excedente" in resposta.text
    assert "Itens por local" in resposta.text
    assert "Itens por categoria" in resposta.text
    assert 'value="2026-06-01"' in resposta.text
    assert 'value="2026-06-30"' in resposta.text


async def test_pagina_estoque_linka_css_e_nav_ativa(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    resposta = await client.get("/relatorios/estoque")

    assert resposta.status_code == 200
    assert "/static/relatorios.css" in resposta.text
    assert (
        'href="/relatorios/estoque" class="ativo" aria-current="page"' in resposta.text
    )


async def test_pagina_estoque_export_preserva_periodo(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    resposta = await client.get(
        "/relatorios/estoque", params={"desde": "2026-06-01", "ate": "2026-06-30"}
    )

    assert (
        "/relatorios/estoque/exportar?desde=2026-06-01&amp;ate=2026-06-30"
        in resposta.text
    )


async def test_pagina_estoque_vazia_exibe_estado_claro(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    resposta = await client.get("/relatorios/estoque")

    assert resposta.status_code == 200
    assert "Nenhum item de estoque no período." in resposta.text


async def test_pagina_transporte_renderiza_agregacoes(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa = await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    with fabrica_sync() as session:
        _snap(
            session,
            empresa.id,
            "transporte",
            "R1",
            origem="SP",
            destino="CWB",
            peso_kg=10.0,
            status="ok",
            previsao_entrega=datetime(2026, 6, 1, tzinfo=UTC),
            data_entrega=datetime(2026, 6, 5, tzinfo=UTC),
        )
        session.commit()

    await _login(client, "a@empresa.com")
    resposta = await client.get("/relatorios/transporte")

    assert resposta.status_code == 200
    assert "Registros por status" in resposta.text
    assert "Peso por rota" in resposta.text
    assert "SP → CWB" in resposta.text


async def test_pagina_e_csv_transporte_exibem_mesma_data(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa = await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    with fabrica_sync() as session:
        _snap(
            session,
            empresa.id,
            "transporte",
            "R1",
            origem="SP",
            destino="CWB",
            peso_kg=10.0,
            status="entregue",
            previsao_entrega=datetime(2026, 6, 10, tzinfo=UTC),
            data_entrega=datetime(2026, 6, 15, tzinfo=UTC),
        )
        session.commit()

    await _login(client, "a@empresa.com")
    pagina = await client.get("/relatorios/transporte")
    exportacao = await client.get("/relatorios/transporte/exportar")

    assert pagina.status_code == 200
    assert "2026-06-10T00:00:00" in pagina.text
    assert _ler_csv(exportacao.content)[1][5] == "2026-06-10T00:00:00"


async def test_pagina_fornecedores_renderiza_indicadores(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa = await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    with fabrica_sync() as session:
        _snap(
            session,
            empresa.id,
            "fornecedores",
            "F1",
            nome="TransLog",
            categoria="transporte",
            prazo_dias=5,
            avaliacao=4.0,
            ativo=True,
        )
        session.commit()

    await _login(client, "a@empresa.com")
    resposta = await client.get("/relatorios/fornecedores")

    assert resposta.status_code == 200
    assert "Distribuição por situação" in resposta.text
    assert "Indicadores" in resposta.text
    assert "Fornecedores por categoria" in resposta.text
    assert "TransLog" in resposta.text


async def test_export_estoque_cabecalho_bom_e_linhas(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa = await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    with fabrica_sync() as session:
        _semear_estoque(session, empresa.id)
        session.commit()

    await _login(client, "a@empresa.com")
    resposta = await client.get(
        "/relatorios/estoque/exportar",
        params={"desde": "2026-06-01", "ate": "2026-06-30"},
    )

    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/csv")
    assert (
        'attachment; filename="relatorio-estoque-2026-06-01_2026-06-30.csv"'
        in resposta.headers["content-disposition"]
    )
    assert resposta.content.startswith(b"\xef\xbb\xbf")
    linhas = _ler_csv(resposta.content)
    assert linhas[0] == [
        "SKU",
        "Nome",
        "Categoria",
        "Local",
        "Quantidade",
        "Mínimo",
        "Situação",
    ]
    assert linhas[1][0] == "S1"
    assert linhas[1][-1] == "Abaixo do mínimo"


async def test_export_transporte_inclui_datas(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa = await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    with fabrica_sync() as session:
        _snap(
            session,
            empresa.id,
            "transporte",
            "R1",
            origem="SP",
            destino="CWB",
            peso_kg=10.0,
            status="entregue",
            previsao_entrega=datetime(2026, 6, 10, tzinfo=UTC),
            data_entrega=datetime(2026, 6, 15, tzinfo=UTC),
        )
        session.commit()

    await _login(client, "a@empresa.com")
    resposta = await client.get("/relatorios/transporte/exportar")

    assert resposta.status_code == 200
    linhas = _ler_csv(resposta.content)
    assert linhas[0][0] == "Código de rastreio"
    assert linhas[1][0] == "R1"
    assert linhas[1][5] == "2026-06-10T00:00:00"
    assert linhas[1][-1] == "Atrasado"


async def test_relatorios_gestor_recebe_200(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "g@empresa.com", papel="gestor")
    await _login(client, "g@empresa.com")

    assert (await client.get("/relatorios/estoque")).status_code == 200
    assert (await client.get("/relatorios/estoque/exportar")).status_code == 200


async def test_export_empresa_vazia_apenas_cabecalho(
    client: AsyncClient, engines: tuple[AsyncEngine, Engine]
) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    resposta = await client.get("/relatorios/estoque/exportar")

    assert resposta.status_code == 200
    linhas = _ler_csv(resposta.content)
    assert len(linhas) == 1
    assert linhas[0][0] == "SKU"
    assert 'filename="relatorio-estoque.csv"' in resposta.headers["content-disposition"]


async def test_relatorios_isolam_entre_tenants_e_ignoram_empresa_id(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa_a = await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    empresa_b = await _criar_usuario_com_empresa(motor_async, "b@empresa.com")
    with fabrica_sync() as session:
        _snap(
            session,
            empresa_a.id,
            "estoque",
            "SKU-A",
            nome="A",
            quantidade=1,
            minimo=5,
        )
        _snap(
            session,
            empresa_b.id,
            "estoque",
            "SKU-B",
            nome="B",
            quantidade=1,
            minimo=5,
        )
        session.commit()

    await _login(client, "a@empresa.com")
    pagina = await client.get(
        "/relatorios/estoque", params={"empresa_id": str(empresa_b.id)}
    )
    exportacao = await client.get(
        "/relatorios/estoque/exportar", params={"empresa_id": str(empresa_b.id)}
    )

    assert pagina.status_code == 200
    assert "SKU-A" in pagina.text
    assert "SKU-B" not in pagina.text
    assert "SKU-B" not in exportacao.content.decode("utf-8-sig")


async def test_export_dominio_invalido_404(client: AsyncClient, engines) -> None:
    motor_async, _ = engines
    await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    await _login(client, "a@empresa.com")

    assert (await client.get("/relatorios/financeiro/exportar")).status_code == 404


async def test_export_fornecedor_fora_da_empresa_nao_aparece(
    client: AsyncClient,
    engines: tuple[AsyncEngine, Engine],
    fabrica_sync: sessionmaker[Session],
) -> None:
    motor_async, _ = engines
    empresa_a = await _criar_usuario_com_empresa(motor_async, "a@empresa.com")
    empresa_b = uuid4()
    with fabrica_sync() as session:
        _snap(
            session,
            empresa_a.id,
            "fornecedores",
            "F-A",
            nome="Fornecedor A",
            categoria="x",
            prazo_dias=1,
            avaliacao=1.0,
            ativo=True,
        )
        _snap(
            session,
            empresa_b,
            "fornecedores",
            "F-B",
            nome="Fornecedor B",
            categoria="x",
            prazo_dias=1,
            avaliacao=1.0,
            ativo=True,
        )
        session.commit()

    await _login(client, "a@empresa.com")
    resposta = await client.get("/relatorios/fornecedores/exportar")

    assert resposta.status_code == 200
    assert "Fornecedor A" in resposta.content.decode("utf-8-sig")
    assert "Fornecedor B" not in resposta.content.decode("utf-8-sig")
