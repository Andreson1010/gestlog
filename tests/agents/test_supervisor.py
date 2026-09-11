"""Testes do agente supervisor."""

from __future__ import annotations

from langchain_core.messages import HumanMessage

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
