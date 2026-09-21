"""Testes do agente supervisor."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from gestlog.agents.supervisor import build_supervisor_prompt, create_supervisor_node


def test_build_supervisor_prompt_lists_specialists() -> None:
    prompt = build_supervisor_prompt()
    for termo in ("transporte", "fornecedores", "estoque", "FINISH"):
        assert termo in prompt


def test_supervisor_node_returns_route(fake_model_cls: type) -> None:
    node = create_supervisor_node(fake_model_cls(routes=["estoque"]))
    decisao = node({"messages": [HumanMessage(content="preciso repor o SKU-200")]})
    assert decisao == {"next": "estoque"}


def test_supervisor_node_defaults_to_finish(fake_model_cls: type) -> None:
    node = create_supervisor_node(fake_model_cls(routes=[]), prompt="roteie")
    decisao = node({"messages": [HumanMessage(content="oi")]})
    assert decisao == {"next": "FINISH"}


def test_supervisor_evita_repetir_especialista_visitado(fake_model_cls: type) -> None:
    model = fake_model_cls(routes=["estoque"])
    node = create_supervisor_node(model)
    estado = {
        "messages": [
            HumanMessage(content="como está o estoque?"),
            AIMessage(content="Resposta logística:\nHá estoque suficiente."),
        ],
        "especialistas_visitados": ["estoque"],
    }

    assert node(estado) == {"next": "FINISH"}
    assert model.mensagens_recebidas


def test_supervisor_permite_especialista_ainda_nao_visitado(
    fake_model_cls: type,
) -> None:
    node = create_supervisor_node(fake_model_cls(routes=["transporte"]))
    estado = {
        "messages": [HumanMessage(content="e o frete?")],
        "especialistas_visitados": ["estoque"],
    }

    assert node(estado) == {"next": "transporte"}
