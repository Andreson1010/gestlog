"""Testes do serviço de copiloto (grafo + contexto do tenant)."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.orm import Session

from gestlog.config import Settings
from gestlog.copilot.service import (
    MENSAGEM_FORA_DE_ESCOPO,
    MENSAGEM_INSUFICIENCIA,
    CopilotService,
    Recomendacao,
    Turno,
    carregar_historico,
    extrair_recomendacao,
)
from gestlog.repositories.catalog import StockRepository
from gestlog.repositories.conversations import (
    ConversationRepository,
    MessageRepository,
    RecommendationRepository,
)
from gestlog.repositories.empresas import EmpresaRepository

_DOMINIOS = ("estoque", "fornecedores", "transporte")


def _tool_comum(
    resposta: str, fontes: str = "", justificativa: str = ""
) -> list[dict[str, Any]]:
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


def _service(
    session: Session,
    model: BaseChatModel,
    empresa_id: UUID,
    user_id: UUID | None = None,
) -> CopilotService:
    return CopilotService(
        session=session,
        empresa_id=empresa_id,
        user_id=user_id or uuid4(),
        model=model,
        settings=Settings(_env_file=None),
    )


def _empresa(session: Session, nome: str) -> UUID:
    empresa = EmpresaRepository(session).create(nome)
    session.commit()
    return empresa.id


def test_answer_roteia_e_responde_em_cada_dominio(
    db_session: Session, fake_model_cls: type
) -> None:
    empresa = _empresa(db_session, "A")
    for dominio in _DOMINIOS:
        model = fake_model_cls(
            routes=[dominio, "FINISH"],
            tool_calls=[_tool_comum(f"resposta de {dominio}", fontes="TMS")],
        )
        resposta = _service(db_session, model, empresa).answer("pergunta")
        assert f"resposta de {dominio}" in resposta
        assert "Fontes: TMS" in resposta


def test_answer_fora_de_escopo(db_session: Session, fake_model_cls: type) -> None:
    empresa = _empresa(db_session, "A")
    model = fake_model_cls(routes=["FINISH"])
    assert _service(db_session, model, empresa).answer("capital da França?") == (
        MENSAGEM_FORA_DE_ESCOPO
    )


def test_answer_sem_fontes_informa_insuficiencia(
    db_session: Session, fake_model_cls: type
) -> None:
    empresa = _empresa(db_session, "A")
    model = fake_model_cls(
        routes=["estoque", "FINISH"],
        tool_calls=[_tool_comum("acho que dá, mas não sei", fontes="")],
    )
    assert _service(db_session, model, empresa).answer("e o estoque?") == (
        MENSAGEM_INSUFICIENCIA
    )


def test_answer_sem_tool_comum_informa_insuficiencia(
    db_session: Session, fake_model_cls: type
) -> None:
    empresa = _empresa(db_session, "A")
    model = fake_model_cls(routes=["estoque", "FINISH"], final="resposta solta")
    assert _service(db_session, model, empresa).answer("e o estoque?") == (
        MENSAGEM_INSUFICIENCIA
    )


def test_answer_injeta_contexto_do_tenant(
    db_session: Session, fake_model_cls: type
) -> None:
    empresa = _empresa(db_session, "A")
    outra = _empresa(db_session, "B")
    repo = StockRepository(db_session)
    repo.upsert(empresa, "SKU-1", "Caixa", 120, 50, "A1")
    repo.upsert(outra, "SKU-1", "Caixa", 7, 1, "Z9")
    db_session.commit()

    model = fake_model_cls(
        routes=["estoque", "FINISH"],
        tool_calls=[_tool_comum("repor", fontes="estoque")],
    )
    _service(db_session, model, empresa).answer("estoque do SKU-1?")

    tools = {tool.name: tool for tool in model.bound_tools}
    assert "quantidade 120" in tools["consultar_estoque"].invoke({"sku": "SKU-1"})
    assert "enviar_resposta_logistica" in tools


def test_tools_do_tenant_isola_entre_empresas(
    db_session: Session, fake_model_cls: type
) -> None:
    empresa = _empresa(db_session, "A")
    outra = _empresa(db_session, "B")
    repo = StockRepository(db_session)
    repo.upsert(empresa, "SKU-1", "Caixa", 120, 50, "A1")
    repo.upsert(outra, "SKU-1", "Caixa", 7, 1, "Z9")
    db_session.commit()

    servico = _service(db_session, fake_model_cls(), empresa)
    tools = {tool.name: tool for tool in servico.tools_por_dominio()["estoque"]}

    assert "quantidade 120" in tools["consultar_estoque"].invoke({"sku": "SKU-1"})
    assert "não encontrado" in tools["consultar_estoque"].invoke({"sku": "SKU-9"})


def test_answer_persiste_turno_no_historico(
    db_session: Session, fake_model_cls: type
) -> None:
    empresa = _empresa(db_session, "A")
    model = fake_model_cls(
        routes=["estoque", "FINISH"],
        tool_calls=[_tool_comum("Há estoque", fontes="estoque")],
    )
    servico = _service(db_session, model, empresa)

    resposta = servico.answer("como está o estoque?")

    assert "Há estoque" in resposta
    turnos = servico.historico()
    assert len(turnos) == 1
    assert turnos[0].pergunta == "como está o estoque?"
    assert turnos[0].resposta == resposta


def test_answer_acumula_turnos_na_mesma_conversa(
    db_session: Session, fake_model_cls: type
) -> None:
    empresa = _empresa(db_session, "A")
    usuario = uuid4()
    servico = _service(
        db_session,
        fake_model_cls(
            routes=["estoque", "FINISH"],
            tool_calls=[_tool_comum("r1", fontes="estoque")],
        ),
        empresa,
        usuario,
    )
    servico.answer("primeira")

    _service(
        db_session,
        fake_model_cls(
            routes=["transporte", "FINISH"],
            tool_calls=[_tool_comum("r2", fontes="TMS")],
        ),
        empresa,
        usuario,
    ).answer("segunda")

    turnos = servico.historico()
    assert [turno.pergunta for turno in turnos] == ["primeira", "segunda"]
    assert "r1" in turnos[0].resposta
    assert "r2" in turnos[1].resposta


def test_historico_isola_entre_empresas(
    db_session: Session, fake_model_cls: type
) -> None:
    empresa = _empresa(db_session, "A")
    outra = _empresa(db_session, "B")
    usuario = uuid4()
    _service(
        db_session,
        fake_model_cls(
            routes=["estoque", "FINISH"],
            tool_calls=[_tool_comum("resposta A", fontes="estoque")],
        ),
        empresa,
        usuario,
    ).answer("pergunta A")

    assert _service(db_session, fake_model_cls(), outra, usuario).historico() == []
    assert "resposta A" in (
        _service(db_session, fake_model_cls(), empresa, usuario).historico()[0].resposta
    )


def test_historico_isola_entre_usuarios(
    db_session: Session, fake_model_cls: type
) -> None:
    empresa = _empresa(db_session, "A")
    usuario = uuid4()
    outro = uuid4()
    _service(
        db_session,
        fake_model_cls(
            routes=["estoque", "FINISH"],
            tool_calls=[_tool_comum("minha resposta", fontes="estoque")],
        ),
        empresa,
        usuario,
    ).answer("minha pergunta")

    assert _service(db_session, fake_model_cls(), empresa, outro).historico() == []


def test_historico_monta_turno_de_pergunta_sem_resposta(
    db_session: Session,
) -> None:
    empresa = _empresa(db_session, "A")
    usuario = uuid4()
    conversa = ConversationRepository(db_session).get_or_create(empresa, usuario)
    MessageRepository(db_session).add_message(conversa.id, "user", "pergunta órfã")
    db_session.commit()

    turnos = carregar_historico(db_session, empresa, usuario)

    assert turnos == [Turno("pergunta órfã", "")]


def test_extrair_recomendacao_estrutura_texto_justificativa_e_fontes() -> None:
    resposta = (
        "Resposta logística:\n"
        "Repor SKU-1\n"
        "Justificativa: abaixo do mínimo\n"
        "Fontes: estoque, TMS"
    )

    recomendacao = extrair_recomendacao(resposta, "estoque")

    assert recomendacao == Recomendacao(
        dominio="estoque",
        texto="Repor SKU-1",
        justificativa="abaixo do mínimo",
        fontes=("estoque", "TMS"),
    )
    assert not recomendacao.insuficiente


def test_extrair_recomendacao_sem_fontes_vira_insuficiencia() -> None:
    resposta = "Resposta logística:\nAlgo sem base\nFontes: não informadas"

    recomendacao = extrair_recomendacao(resposta, "estoque")

    assert recomendacao.insuficiente
    assert recomendacao.texto == MENSAGEM_INSUFICIENCIA
    assert recomendacao.fontes == ()


def test_extrair_recomendacao_fora_de_escopo_preserva_mensagem() -> None:
    recomendacao = extrair_recomendacao(MENSAGEM_FORA_DE_ESCOPO, "")

    assert recomendacao.insuficiente
    assert recomendacao.texto == MENSAGEM_FORA_DE_ESCOPO


def test_answer_persiste_recomendacao_na_conversa(
    db_session: Session, fake_model_cls: type
) -> None:
    empresa = _empresa(db_session, "A")
    usuario = uuid4()
    model = fake_model_cls(
        routes=["estoque", "FINISH"],
        tool_calls=[
            _tool_comum("Repor SKU-1", fontes="estoque, ERP", justificativa="abaixo")
        ],
    )

    _service(db_session, model, empresa, usuario).answer("o que fazer?")

    conversa = ConversationRepository(db_session).get_by_user(empresa, usuario)
    assert conversa is not None
    recomendacoes = RecommendationRepository(db_session).list_by_conversation(
        conversa.id
    )
    assert len(recomendacoes) == 1
    assert recomendacoes[0].dominio == "estoque"
    assert recomendacoes[0].texto == "Repor SKU-1"
    assert recomendacoes[0].justificativa == "abaixo"
    assert recomendacoes[0].fontes == ["estoque", "ERP"]


def test_insuficiencia_nao_persiste_recomendacao(
    db_session: Session, fake_model_cls: type
) -> None:
    empresa = _empresa(db_session, "A")
    usuario = uuid4()
    model = fake_model_cls(routes=["estoque", "FINISH"], final="resposta solta")

    _service(db_session, model, empresa, usuario).answer("o que fazer?")

    conversa = ConversationRepository(db_session).get_by_user(empresa, usuario)
    assert conversa is not None
    assert RecommendationRepository(db_session).list_by_conversation(conversa.id) == []
