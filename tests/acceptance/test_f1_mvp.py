"""Testes de aceitação P1 da F1 (ponta a ponta, sem rede).

Cobre os critérios de `spec.md`: ACC-01..04, ING-01..03, COP-01..06, SEC-01..03 e
QUA-01..02. O modelo de chat é o fake injetado (nenhum teste toca Ollama).
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import Session, sessionmaker

from gestlog.audit import purgar_expiradas
from gestlog.auth import get_async_session
from gestlog.config import Settings, get_settings
from gestlog.copilot.service import MENSAGEM_INSUFICIENCIA, MENSAGEM_QUOTA_EXCEDIDA
from gestlog.db.models import (
    AuditLog,
    Conversation,
    Empresa,
    Membership,
    UsageRecord,
    User,
)
from gestlog.db.session import (
    build_async_engine,
    build_async_session_factory,
    build_engine,
    build_session_factory,
    init_async_db,
)
from gestlog.evaluation import CasoGolden, run_golden_set
from gestlog.web import create_app, get_chat_model, get_sync_session

_SENHA = "senha-secreta-123"
_COOKIE = "gestlog_auth"
_ESTOQUE = "estoque"
_FONTES = "estoque"
_ROTULO_PII = "[NOME]"


def _tool_comum(
    resposta: str, fontes: str = _FONTES, justificativa: str = "porque sim"
) -> list[dict[str, object]]:
    return [
        {
            "name": "enviar_resposta_logistica",
            "args": {
                "resposta": resposta,
                "fontes": fontes,
                "justificativa": justificativa,
            },
            "id": "call-1",
            "type": "tool_call",
        }
    ]


def _montar_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "database_url": "sqlite+aiosqlite:///:memory:",
        "auth_secret": "segredo-de-teste-com-pelo-menos-32-bytes",
        "auth_cookie_secure": False,
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def _settings() -> Settings:
    return _montar_settings()


def _settings_quota_baixa() -> Settings:
    return _montar_settings(llm_monthly_token_quota=1)


@pytest.fixture
async def motores(tmp_path: Path) -> AsyncIterator[tuple[AsyncEngine, Engine]]:
    banco = tmp_path / "f1.db"
    motor_async = build_async_engine(
        Settings(_env_file=None, database_url=f"sqlite+aiosqlite:///{banco}")
    )
    await init_async_db(motor_async)
    motor_sync = build_engine(
        Settings(_env_file=None, database_url=f"sqlite+pysqlite:///{banco}")
    )
    yield motor_async, motor_sync
    await motor_async.dispose()
    motor_sync.dispose()


@pytest.fixture
def fabrica_sync(motores: tuple[AsyncEngine, Engine]) -> sessionmaker[Session]:
    _, motor_sync = motores
    return build_session_factory(motor_sync)


@pytest.fixture
async def app(motores: tuple[AsyncEngine, Engine]) -> AsyncIterator[FastAPI]:
    motor_async, motor_sync = motores
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


def _usar_modelo(app: FastAPI, model: object) -> None:
    app.dependency_overrides[get_chat_model] = lambda: model


async def _criar_conta(client: AsyncClient, empresa: str, email: str) -> None:
    resposta = await client.post(
        "/onboarding",
        json={"nome_empresa": empresa, "email": email, "senha": _SENHA},
    )
    assert resposta.status_code == 201, resposta.text


async def _login(client: AsyncClient, email: str) -> None:
    resposta = await client.post(
        "/auth/login", data={"username": email, "password": _SENHA}
    )
    assert resposta.status_code == 204, resposta.text
    assert client.cookies.get(_COOKIE)


async def _conversar(client: AsyncClient, pergunta: str) -> str:
    resposta = await client.get("/chat/stream", params={"pergunta": pergunta})
    assert resposta.status_code == 200
    return resposta.text


def _empresa_id(fabrica: sessionmaker[Session], email: str) -> UUID:
    with fabrica() as session:
        usuario = (
            session.execute(select(User).where(User.email == email)).scalars().first()
        )
        assert usuario is not None
        vinculo = (
            session.execute(select(Membership).where(Membership.user_id == usuario.id))
            .scalars()
            .first()
        )
        assert vinculo is not None
        return vinculo.empresa_id


def _recomendacao_id(html: str) -> UUID:
    casado = re.search(r"/recomendacoes/([0-9a-f-]+)/feedback", html)
    assert casado is not None, html
    return UUID(casado.group(1))


async def test_acc_01_admin_cria_conta_e_administra_o_tenant(
    client: AsyncClient,
) -> None:
    await _criar_conta(client, "Logística A", "admin@a.com")
    await _login(client, "admin@a.com")

    resposta = await client.get("/empresa/usuarios")

    assert resposta.status_code == 200
    itens = resposta.json()
    assert len(itens) == 1
    assert itens[0]["email"] == "admin@a.com"
    assert itens[0]["papel"] == "admin"


async def test_acc_02_login_da_sessao_vinculada_ao_tenant(client: AsyncClient) -> None:
    await _criar_conta(client, "Logística B", "admin@b.com")
    await _login(client, "admin@b.com")

    assert (await client.get("/kpis")).status_code == 200
    assert (await client.get("/chat")).status_code == 200


async def test_acc_03_convite_da_acesso_com_papel(client: AsyncClient) -> None:
    await _criar_conta(client, "Logística C", "admin@c.com")
    await _login(client, "admin@c.com")

    convite = await client.post(
        "/empresa/convites",
        json={"email": "op@c.com", "papel": "operador", "senha": _SENHA},
    )
    assert convite.status_code == 201
    assert convite.json()["papel"] == "operador"

    await _login(client, "op@c.com")
    assert (await client.get("/chat")).status_code == 200
    assert (await client.get("/kpis")).status_code == 403


async def test_acc_04_consultas_ficam_no_tenant(
    client: AsyncClient,
    app: FastAPI,
    fake_model_cls: type,
) -> None:
    _usar_modelo(
        app,
        fake_model_cls(
            routes=["estoque", "FINISH"],
            tool_calls=[_tool_comum("segredo-do-tenant-A", fontes=_FONTES)],
        ),
    )
    await _criar_conta(client, "A", "a@tenant.com")
    await _login(client, "a@tenant.com")
    await _conversar(client, "pergunta exclusiva A")

    await _criar_conta(client, "B", "b@tenant.com")
    _usar_modelo(
        app,
        fake_model_cls(
            routes=["estoque", "FINISH"],
            tool_calls=[_tool_comum("segredo-do-tenant-B", fontes=_FONTES)],
        ),
    )
    await _login(client, "b@tenant.com")
    historico = await client.get("/chat")

    assert "pergunta exclusiva A" not in historico.text
    assert "segredo-do-tenant-A" not in historico.text


async def test_acc_05_sem_sessao_bloqueia_recursos(client: AsyncClient) -> None:
    assert (await client.get("/kpis")).status_code == 401
    chat = await client.get("/chat", follow_redirects=False)
    assert chat.status_code == 303
    assert chat.headers["location"] == "/login"


async def test_ing_01_importa_csv_valido(
    client: AsyncClient,
) -> None:
    await _criar_conta(client, "ING", "admin@ing.com")
    await _login(client, "admin@ing.com")
    conteudo = b"sku,nome,quantidade,minimo,local\nSKU-1,Caixa,10,2,A1\n"

    resposta = await client.post(
        "/importar",
        data={"tipo": _ESTOQUE},
        files={"arquivo": ("estoque.csv", conteudo, "text/csv")},
    )

    assert resposta.status_code == 200
    assert "1 aceitas" in resposta.text


async def test_ing_02_linha_invalida_e_reportada_sem_abortar(
    client: AsyncClient,
) -> None:
    await _criar_conta(client, "ING", "admin@ing.com")
    await _login(client, "admin@ing.com")
    conteudo = b"sku,nome,quantidade,minimo\nSKU-1,Caixa,10,2\n,Caixa,3,1\n"

    resposta = await client.post(
        "/importar",
        data={"tipo": _ESTOQUE},
        files={"arquivo": ("estoque.csv", conteudo, "text/csv")},
    )

    assert resposta.status_code == 200
    assert "1 aceitas" in resposta.text
    assert "1 rejeitadas" in resposta.text
    assert "Linha 3" in resposta.text


async def test_ing_03_historico_por_tenant(client: AsyncClient) -> None:
    await _criar_conta(client, "ING", "admin@ing.com")
    await _login(client, "admin@ing.com")
    await client.post(
        "/importar",
        data={"tipo": _ESTOQUE},
        files={
            "arquivo": (
                "e.csv",
                b"sku,nome,quantidade,minimo\nSKU-9,X,1,1\n",
                "text/csv",
            )
        },
    )

    historico = await client.get("/importar/historico")

    assert historico.status_code == 200
    assert _ESTOQUE in historico.text
    assert "concluido" in historico.text


async def test_cop_01_roteia_dominios_e_responde(
    client: AsyncClient, app: FastAPI, fake_model_cls: type
) -> None:
    await _criar_conta(client, "COP", "op@cop.com")
    await _login(client, "op@cop.com")

    for dominio in ("estoque", "fornecedores", "transporte"):
        _usar_modelo(
            app,
            fake_model_cls(
                routes=[dominio, "FINISH"],
                tool_calls=[_tool_comum(f"resposta de {dominio}", fontes=dominio)],
            ),
        )
        texto = await _conversar(client, f"pergunta de {dominio}")
        assert f"resposta de {dominio}" in texto


async def test_cop_02_usa_ferramentas_read_only(
    client: AsyncClient, app: FastAPI, fake_model_cls: type
) -> None:
    model = fake_model_cls(
        routes=["estoque", "FINISH"],
        tool_calls=[_tool_comum("repor", fontes=_FONTES)],
    )
    _usar_modelo(app, model)
    await _criar_conta(client, "COP", "op@cop.com")
    await _login(client, "op@cop.com")
    await _conversar(client, "estoque do SKU-1?")

    nomes = {tool.name for tool in model.bound_tools}
    assert "consultar_estoque" in nomes
    assert "enviar_resposta_logistica" in nomes


async def test_cop_03_sem_base_informa_insuficiencia(
    client: AsyncClient, app: FastAPI, fake_model_cls: type
) -> None:
    _usar_modelo(
        app,
        fake_model_cls(
            routes=["estoque", "FINISH"],
            tool_calls=[_tool_comum("acho que dá", fontes="")],
        ),
    )
    await _criar_conta(client, "COP", "op@cop.com")
    await _login(client, "op@cop.com")

    texto = await _conversar(client, "e o estoque?")

    assert MENSAGEM_INSUFICIENCIA in texto


async def test_cop_04_recomendacao_explicada(
    client: AsyncClient, app: FastAPI, fake_model_cls: type
) -> None:
    _usar_modelo(
        app,
        fake_model_cls(
            routes=["estoque", "FINISH"],
            tool_calls=[
                _tool_comum(
                    "Repor SKU-1", fontes=_FONTES, justificativa="abaixo do mínimo"
                )
            ],
        ),
    )
    await _criar_conta(client, "COP", "op@cop.com")
    await _login(client, "op@cop.com")

    texto = await _conversar(client, "o que fazer?")

    assert "Repor SKU-1" in texto
    assert "Justificativa: abaixo do mínimo" in texto
    assert f"Fontes: {_FONTES}" in texto


async def test_cop_05_fora_de_escopo(
    client: AsyncClient, app: FastAPI, fake_model_cls: type
) -> None:
    _usar_modelo(app, fake_model_cls(routes=["FINISH"]))
    await _criar_conta(client, "COP", "op@cop.com")
    await _login(client, "op@cop.com")

    texto = await _conversar(client, "qual a capital da França?")

    assert "não cobre" in texto.lower() or "não encontrei" in texto.lower()


async def test_cop_06_resposta_em_streaming(
    client: AsyncClient, app: FastAPI, fake_model_cls: type
) -> None:
    _usar_modelo(
        app,
        fake_model_cls(
            routes=["estoque", "FINISH"],
            tool_calls=[_tool_comum("repor", fontes=_FONTES)],
        ),
    )
    await _criar_conta(client, "COP", "op@cop.com")
    await _login(client, "op@cop.com")

    resposta = await client.get("/chat/stream", params={"pergunta": "estoque?"})

    assert resposta.headers["content-type"].startswith("text/event-stream")
    assert "event: resposta" in resposta.text
    assert "event: fim" in resposta.text


async def test_cop_aceite_registra_decisao_e_historico(
    client: AsyncClient, app: FastAPI, fake_model_cls: type
) -> None:
    _usar_modelo(
        app,
        fake_model_cls(
            routes=["estoque", "FINISH"],
            tool_calls=[_tool_comum("Repor SKU-1", fontes=_FONTES)],
        ),
    )
    await _criar_conta(client, "COP", "op@cop.com")
    await _login(client, "op@cop.com")
    await _conversar(client, "o que fazer?")

    pagina = await client.get("/chat")
    recommendation_id = _recomendacao_id(pagina.text)
    feedback = await client.post(
        f"/recomendacoes/{recommendation_id}/feedback", data={"decisao": "aceita"}
    )
    assert feedback.status_code == 200
    assert "aceita" in feedback.text

    recarregada = await client.get("/chat")
    assert "Decisão: aceita" in recarregada.text


async def test_sec_01_pii_nao_vai_ao_llm(
    client: AsyncClient, app: FastAPI, fake_model_cls: type
) -> None:
    model = fake_model_cls(
        routes=["estoque", "FINISH"],
        tool_calls=[_tool_comum("ok", fontes=_FONTES)],
    )
    _usar_modelo(app, model)
    await _criar_conta(client, "SEC", "op@sec.com")
    await _login(client, "op@sec.com")

    await _conversar(client, "Falar com João Silva no (11) 98765-4321")

    prompt = "\n".join(
        str(mensagem.content) for lote in model.mensagens_recebidas for mensagem in lote
    )
    assert "João" not in prompt
    assert "98765" not in prompt
    assert _ROTULO_PII in prompt


async def test_sec_02_retencao_purga_conversa_vencida(
    fabrica_sync: sessionmaker[Session],
) -> None:
    with fabrica_sync() as session:
        empresa = Empresa(nome="SEC", retention_days=30)
        session.add(empresa)
        session.flush()
        conversa = Conversation(empresa_id=empresa.id, user_id=uuid4())
        conversa.created_at = datetime.now(UTC) - timedelta(days=60)
        session.add(conversa)
        session.commit()

        removidas = purgar_expiradas(session, settings=Settings(_env_file=None))
        assert removidas == 1
        assert session.get(Conversation, conversa.id) is None


async def test_sec_03_interacao_gera_auditoria(
    client: AsyncClient,
    app: FastAPI,
    fake_model_cls: type,
    fabrica_sync: sessionmaker[Session],
) -> None:
    _usar_modelo(
        app,
        fake_model_cls(
            routes=["estoque", "FINISH"],
            tool_calls=[_tool_comum("Repor", fontes=_FONTES)],
        ),
    )
    await _criar_conta(client, "SEC", "op@sec.com")
    await _login(client, "op@sec.com")
    await _conversar(client, "o que fazer?")

    with fabrica_sync() as session:
        eventos = session.execute(select(AuditLog.evento)).scalars().all()

    assert "pergunta" in eventos
    assert "recomendacao" in eventos


def test_qua_01_golden_set_reporta_qualidade(fake_model_cls: type) -> None:
    casos = (CasoGolden("e1", "estoque?", "estoque", (_FONTES,)),)
    model = fake_model_cls(
        routes=["estoque", "FINISH"],
        tool_calls=[_tool_comum("repor", fontes=_FONTES)],
    )

    relatorio = run_golden_set(casos, model, Settings(_env_file=None))

    assert relatorio.total == 1
    assert relatorio.acuracia == 1.0
    assert relatorio.alucinacoes == 0
    assert relatorio.fontes_corretas == 1


async def test_qua_02_mede_uso_e_bloqueia_quota(
    client: AsyncClient,
    app: FastAPI,
    fake_model_cls: type,
    fabrica_sync: sessionmaker[Session],
) -> None:
    await _criar_conta(client, "QUA", "op@qua.com")
    _usar_modelo(
        app,
        fake_model_cls(
            routes=["estoque", "FINISH"],
            tool_calls=[_tool_comum("repor", fontes=_FONTES)],
            tokens=10,
        ),
    )
    await _login(client, "op@qua.com")
    await _conversar(client, "estoque?")

    empresa_id = _empresa_id(fabrica_sync, "op@qua.com")
    with fabrica_sync() as session:
        total = session.execute(
            select(func.count())
            .select_from(UsageRecord)
            .where(UsageRecord.empresa_id == empresa_id)
        ).scalar_one()
    assert total >= 1

    app.dependency_overrides[get_settings] = _settings_quota_baixa
    texto = await _conversar(client, "estoque?")
    assert MENSAGEM_QUOTA_EXCEDIDA in texto
