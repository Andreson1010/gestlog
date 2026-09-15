"""Testes do serviço de copiloto (grafo + contexto do tenant)."""

from __future__ import annotations

from uuid import UUID, uuid4

from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.orm import Session

from gestlog.config import Settings
from gestlog.copilot.service import MENSAGEM_FORA_DE_ESCOPO, CopilotService
from gestlog.repositories.catalog import StockRepository
from gestlog.repositories.empresas import EmpresaRepository

_DOMINIOS = ("estoque", "fornecedores", "transporte")


def _service(
    session: Session,
    model: BaseChatModel,
    empresa_id: UUID,
) -> CopilotService:
    return CopilotService(
        session=session,
        empresa_id=empresa_id,
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
            routes=[dominio, "FINISH"], final=f"resposta de {dominio}"
        )
        assert _service(db_session, model, empresa).answer("pergunta") == (
            f"resposta de {dominio}"
        )


def test_answer_fora_de_escopo(db_session: Session, fake_model_cls: type) -> None:
    empresa = _empresa(db_session, "A")
    model = fake_model_cls(routes=["FINISH"])
    assert _service(db_session, model, empresa).answer("capital da França?") == (
        MENSAGEM_FORA_DE_ESCOPO
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

    model = fake_model_cls(routes=["estoque", "FINISH"], final="ok")
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


def test_empresa_sem_dados_responde_sem_quebrar(
    db_session: Session, fake_model_cls: type
) -> None:
    model = fake_model_cls(routes=["estoque", "FINISH"], final="sem dados")
    servico = _service(db_session, model, uuid4())
    assert servico.answer("e o estoque?") == "sem dados"
