"""Aceitação F2 (HITL): o chat permanece read-only (AD-002)."""

from __future__ import annotations

from uuid import UUID

from f2_suporte import (
    TOOLS_ESTOQUE,
    TOOLS_FORNECEDORES,
    TOOLS_TRANSPORTE,
    criar_conta,
    eventos_auditoria,
    login,
    tool_comum,
    usar_modelo,
)
from fastapi import FastAPI
from httpx import AsyncClient
from langchain_core.messages import HumanMessage
from sqlalchemy.orm import Session, sessionmaker

from gestlog.agents.inventory import build_inventory_node
from gestlog.agents.suppliers import build_suppliers_node
from gestlog.agents.transport import build_transport_node


def test_chat_read_only_sem_tool_de_escrita(fake_model_cls: type) -> None:
    for builder, esperado in (
        (build_inventory_node, TOOLS_ESTOQUE),
        (build_suppliers_node, TOOLS_FORNECEDORES),
        (build_transport_node, TOOLS_TRANSPORTE),
    ):
        model = fake_model_cls(final="ok")
        node = builder(model, max_steps=2)
        node({"messages": [HumanMessage(content="x")]})
        assert {tool.name for tool in model.bound_tools} == esperado


async def test_chat_turno_nao_gera_eventos_de_correcao(
    client: AsyncClient,
    app: FastAPI,
    fake_model_cls: type,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    usar_modelo(
        app,
        fake_model_cls(routes=["estoque", "FINISH"], tool_calls=[tool_comum("repor")]),
    )
    await login(client, "a@tenant.com")

    await client.get("/chat/stream", params={"pergunta": "estoque?"})

    eventos = {evento.evento for evento in eventos_auditoria(fabrica_sync, empresa_id)}
    assert eventos <= {"pergunta", "recomendacao"}
    assert not any(evento.startswith("correcao_") for evento in eventos)
