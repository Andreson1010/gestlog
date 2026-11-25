"""Testes unitários da medição de uso e da quota mensal."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from uuid import UUID

import pytest
from apoio import criar_usuario
from sqlalchemy.orm import Session

from gestlog.config import Settings
from gestlog.copilot.metering import (
    QuotaExcedida,
    check_quota,
    check_teto_global,
    quota_da_empresa,
    record_usage,
    travar_empresa,
    uso_no_mes,
)
from gestlog.copilot.service import (
    MENSAGEM_FORA_DE_ESCOPO,
    MENSAGEM_QUOTA_EXCEDIDA,
    CopilotService,
)
from gestlog.db import build_session_factory
from gestlog.repositories.empresas import EmpresaRepository
from gestlog.repositories.telemetry import UsageRepository


def _empresa(session: Session, nome: str) -> UUID:
    empresa = EmpresaRepository(session).create(nome)
    session.commit()
    return empresa.id


def _turno_tool(resposta: str) -> list[dict]:
    return [
        {
            "name": "enviar_resposta_logistica",
            "args": {"resposta": resposta, "fontes": "estoque"},
            "id": "call-1",
            "type": "tool_call",
        }
    ]


def test_turno_so_supervisor_conta_tokens(
    db_session: Session, fake_model_cls: type
) -> None:
    """Turno com rota FINISH direta registra tokens do supervisor, sem metadata (C-1)."""
    empresa = _empresa(db_session, "A")
    servico = CopilotService(
        session=db_session,
        empresa_id=empresa,
        user_id=criar_usuario(db_session),
        model=fake_model_cls(routes=["FINISH"]),
        settings=Settings(_env_file=None),
    )

    resposta, _ = servico.answer_com_recomendacao("capital da França?")

    assert resposta == MENSAGEM_FORA_DE_ESCOPO
    registros = UsageRepository(db_session).list(empresa)
    assert len(registros) == 1
    assert registros[0].tokens > 0


def test_record_usage_soma_por_empresa(db_session: Session) -> None:
    empresa = _empresa(db_session, "A")
    outra = _empresa(db_session, "B")

    record_usage(db_session, empresa, "qwen", 100)
    record_usage(db_session, empresa, "qwen", 50)
    record_usage(db_session, outra, "qwen", 10)
    db_session.commit()

    repo = UsageRepository(db_session)
    assert repo.total_tokens(empresa) == 150
    assert repo.total_tokens(outra) == 10


def test_record_usage_rejeita_tokens_negativos(db_session: Session) -> None:
    empresa = _empresa(db_session, "A")

    with pytest.raises(ValueError):
        record_usage(db_session, empresa, "qwen", -1)


def test_uso_no_mes_soma_apenas_mes_corrente(db_session: Session) -> None:
    empresa = _empresa(db_session, "A")
    agora = datetime(2026, 6, 15, 12, tzinfo=UTC)
    repo = UsageRepository(db_session)
    antigo = repo.record(empresa, "qwen", 999)
    antigo.created_at = datetime(2026, 5, 20, 12, tzinfo=UTC)
    atual = repo.record(empresa, "qwen", 100)
    atual.created_at = agora
    db_session.commit()

    assert uso_no_mes(db_session, empresa, agora) == 100


def test_uso_no_mes_rejeita_datetime_sem_fuso(db_session: Session) -> None:
    empresa = _empresa(db_session, "A")

    with pytest.raises(ValueError):
        uso_no_mes(db_session, empresa, datetime(2026, 1, 1))


def test_check_quota_permite_abaixo(db_session: Session) -> None:
    empresa = EmpresaRepository(db_session).get(_empresa(db_session, "A"))
    record_usage(db_session, empresa.id, "qwen", 50)
    db_session.commit()
    settings = Settings(_env_file=None, llm_monthly_token_quota=100)

    assert check_quota(db_session, empresa, settings) == 50


def test_check_quota_bloqueia_ao_atingir(db_session: Session) -> None:
    empresa = EmpresaRepository(db_session).get(_empresa(db_session, "A"))
    record_usage(db_session, empresa.id, "qwen", 100)
    db_session.commit()
    settings = Settings(_env_file=None, llm_monthly_token_quota=100)

    with pytest.raises(QuotaExcedida) as excinfo:
        check_quota(db_session, empresa, settings)

    assert excinfo.value.usado == 100
    assert excinfo.value.quota == 100
    assert excinfo.value.empresa_id == empresa.id


def test_check_quota_isola_entre_empresas(db_session: Session) -> None:
    empresa = EmpresaRepository(db_session).get(_empresa(db_session, "A"))
    outra = EmpresaRepository(db_session).get(_empresa(db_session, "B"))
    record_usage(db_session, empresa.id, "qwen", 100)
    db_session.commit()
    settings = Settings(_env_file=None, llm_monthly_token_quota=100)

    assert check_quota(db_session, outra, settings) == 0


def test_quota_da_empresa_sobrepoe_o_global_e_null_cai_para_settings(
    db_session: Session,
) -> None:
    """QUO-04: coluna própria vence; NULL herda o teto global do Settings."""
    settings = Settings(_env_file=None, llm_monthly_token_quota=1000)
    repo = EmpresaRepository(db_session)
    propria = repo.create("Propria", token_quota_mensal=50)
    herdada = repo.create("Herdada")
    db_session.commit()

    assert quota_da_empresa(propria, settings) == 50
    assert quota_da_empresa(herdada, settings) == 1000


def test_check_quota_usa_quota_da_empresa_travada(db_session: Session) -> None:
    """A empresa travada dita a quota; consumo histórico conta sem reset (I-8/EDG-12)."""
    settings = Settings(_env_file=None, llm_monthly_token_quota=1_000_000)
    repo = EmpresaRepository(db_session)
    empresa = repo.create("A", token_quota_mensal=50)
    record_usage(db_session, empresa.id, "qwen", 50)
    db_session.commit()

    travada = travar_empresa(db_session, empresa.id)

    with pytest.raises(QuotaExcedida) as excinfo:
        check_quota(db_session, travada, settings)

    assert excinfo.value.quota == 50
    assert excinfo.value.usado == 50


def test_teto_global_bloqueia_somatorio(db_session: Session) -> None:
    """QUO-05: a salvaguarda soma TODAS as empresas do mês."""
    settings = Settings(_env_file=None, llm_monthly_token_quota=100)
    a = _empresa(db_session, "A")
    b = _empresa(db_session, "B")
    record_usage(db_session, a, "qwen", 60)
    record_usage(db_session, b, "qwen", 40)
    db_session.commit()
    agora = datetime.now(UTC)

    with pytest.raises(QuotaExcedida) as excinfo:
        check_teto_global(db_session, settings, agora)

    assert excinfo.value.usado == 100
    assert excinfo.value.quota == 100


def test_teto_global_com_folga_nao_bloqueia(db_session: Session) -> None:
    settings = Settings(_env_file=None, llm_monthly_token_quota=100)
    a = _empresa(db_session, "A")
    b = _empresa(db_session, "B")
    record_usage(db_session, a, "qwen", 60)
    record_usage(db_session, b, "qwen", 39)
    db_session.commit()

    assert check_teto_global(db_session, settings, datetime.now(UTC)) is None


def test_teto_global_rejeita_datetime_sem_fuso(db_session: Session) -> None:
    settings = Settings(_env_file=None)

    with pytest.raises(ValueError):
        check_teto_global(db_session, settings, datetime(2026, 1, 1))


def test_create_empresa_recusa_quota_nao_positiva(db_session: Session) -> None:
    repo = EmpresaRepository(db_session)

    with pytest.raises(ValueError):
        repo.create("Zero", token_quota_mensal=0)

    with pytest.raises(ValueError):
        repo.create("Negativa", token_quota_mensal=-5)


def test_quota_estourada_devolve_mensagem_nao_500(
    db_session: Session, fake_model_cls: type
) -> None:
    """QUO-06: quota da empresa estourada vira mensagem explícita, sem chamar o LLM."""
    repo = EmpresaRepository(db_session)
    empresa = repo.create("A", token_quota_mensal=10)
    record_usage(db_session, empresa.id, "qwen", 10)
    db_session.commit()
    model = fake_model_cls(
        routes=["estoque", "FINISH"],
        tool_calls=[_turno_tool("repor")],
    )
    servico = CopilotService(
        session=db_session,
        empresa_id=empresa.id,
        user_id=criar_usuario(db_session),
        model=model,
        settings=Settings(_env_file=None, llm_monthly_token_quota=1_000_000),
    )

    resposta, recomendacao_id = servico.answer_com_recomendacao("estoque?")

    assert resposta == MENSAGEM_QUOTA_EXCEDIDA
    assert recomendacao_id is None
    assert model.mensagens_recebidas == []


def test_empresa_b_nao_bloqueada_pela_a(
    db_session: Session, fake_model_cls: type
) -> None:
    """EDG-02: a quota esgotada da A não impede o turno da B."""
    repo = EmpresaRepository(db_session)
    a = repo.create("A", token_quota_mensal=10)
    b = repo.create("B")
    record_usage(db_session, a.id, "qwen", 10)
    db_session.commit()
    settings = Settings(_env_file=None, llm_monthly_token_quota=1_000_000)
    model = fake_model_cls(
        routes=["estoque", "FINISH"],
        tool_calls=[_turno_tool("repor")],
    )
    servico = CopilotService(
        session=db_session,
        empresa_id=b.id,
        user_id=criar_usuario(db_session),
        model=model,
        settings=settings,
    )

    with pytest.raises(QuotaExcedida):
        check_quota(db_session, a, settings)

    assert servico.answer("estoque?") == "repor"
    assert UsageRepository(db_session).list(b.id)


def test_corrida_da_quota_tem_um_vencedor_somente(engine_postgres) -> None:
    """I-8/EDG-01: dois turnos paralelos da mesma empresa produzem um vencedor."""
    if engine_postgres is None:
        pytest.skip("a corrida real exige o Postgres da matriz de dialetos")
    factory = build_session_factory(engine_postgres)
    settings = Settings(_env_file=None, llm_monthly_token_quota=1_000_000)
    with factory() as preparo:
        repo = EmpresaRepository(preparo)
        empresa = repo.create("Corrida", token_quota_mensal=10)
        preparo.commit()
        empresa_id = empresa.id
    resultados: list[str] = []

    def turno() -> None:
        with factory() as sessao:
            try:
                travada = travar_empresa(sessao, empresa_id)
                check_quota(sessao, travada, settings)
                record_usage(sessao, empresa_id, "qwen", 10)
                sessao.commit()
                resultados.append("venceu")
            except QuotaExcedida:
                resultados.append("bloqueado")

    fios = [threading.Thread(target=turno, daemon=True) for _ in range(2)]
    for fio in fios:
        fio.start()
    for fio in fios:
        fio.join(timeout=60)

    assert sorted(resultados) == ["bloqueado", "venceu"]
    with factory() as conferencia:
        registros = UsageRepository(conferencia).list(empresa_id)
        assert len(registros) == 1
        assert sum(r.tokens for r in registros) == 10


def test_lock_por_linha_nao_bloqueia_outra_empresa(engine_postgres) -> None:
    """EDG-02: o lock de quota é por linha; A travada não segura B."""
    if engine_postgres is None:
        pytest.skip("a contenção real de lock exige o Postgres da matriz de dialetos")
    factory = build_session_factory(engine_postgres)
    with factory() as preparo:
        repo = EmpresaRepository(preparo)
        a = repo.create("A", token_quota_mensal=10)
        b = repo.create("B", token_quota_mensal=10)
        preparo.commit()

    with factory() as sessao_a:
        travar_empresa(sessao_a, a.id)
        with factory() as sessao_b:
            travar_empresa(sessao_b, b.id)
            sessao_b.rollback()
        sessao_a.rollback()
