"""Testes do agente supervisor."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from gestlog.agents.supervisor import build_supervisor_prompt, create_supervisor_node


def test_build_supervisor_prompt_lists_specialists() -> None:
    prompt = build_supervisor_prompt()
    for termo in ("transporte", "fornecedores", "estoque", "FINISH"):
        assert termo in prompt


def test_supervisor_node_returns_route(fake_model_cls: type) -> None:
    node = create_supervisor_node(fake_model_cls(routes=["estoque"]))
    decisao = node({"messages": [HumanMessage(content="preciso repor o SKU-200")]})
    assert decisao["next"] == "estoque"
    assert decisao["tokens_usados"] >= 1


def test_supervisor_node_defaults_to_finish(fake_model_cls: type) -> None:
    node = create_supervisor_node(fake_model_cls(routes=[]), prompt="roteie")
    decisao = node({"messages": [HumanMessage(content="oi")]})
    assert decisao["next"] == "FINISH"


def test_supervisor_soma_tokens_do_roteamento(fake_model_cls: type) -> None:
    """O roteamento do supervisor conta tokens no estado, com ou sem metadata (C-1)."""
    estimado = create_supervisor_node(fake_model_cls(routes=["estoque"]))
    reportado = create_supervisor_node(fake_model_cls(routes=["estoque"], tokens=10))
    estado = {"messages": [HumanMessage(content="preciso repor o SKU-200")]}

    assert estimado(estado)["tokens_usados"] >= 1
    assert reportado(estado)["tokens_usados"] == 10


def test_supervisor_route_malformada_vira_finish() -> None:
    """Resposta do roteador sem ``parsed`` (parsing_error) encerra como hoje."""

    class _RoteadorMalformado:
        def with_structured_output(self, _schema: type, **_: object) -> Any:
            return self

        def invoke(self, messages: list[Any]) -> dict[str, Any]:
            return {"raw": AIMessage(content="lixo"), "parsing_error": Exception()}

    node = create_supervisor_node(_RoteadorMalformado())
    decisao = node({"messages": [HumanMessage(content="oi")]})

    assert decisao["next"] == "FINISH"
    assert decisao["tokens_usados"] >= 1


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

    assert node(estado)["next"] == "FINISH"
    assert model.mensagens_recebidas


def test_supervisor_permite_especialista_ainda_nao_visitado(
    fake_model_cls: type,
) -> None:
    node = create_supervisor_node(fake_model_cls(routes=["transporte"]))
    estado = {
        "messages": [HumanMessage(content="e o frete?")],
        "especialistas_visitados": ["estoque"],
    }

    assert node(estado)["next"] == "transporte"
