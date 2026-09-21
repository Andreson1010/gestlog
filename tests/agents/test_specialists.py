"""Testes dos nós especialistas (loop de ferramentas)."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage

from gestlog.agents.inventory import build_inventory_node
from gestlog.agents.suppliers import build_suppliers_node
from gestlog.agents.transport import build_transport_node


def _tool_call(name: str, args: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"name": name, "args": args, "id": "call-1", "type": "tool_call"}]


def test_transport_node_executes_tool(fake_model_cls: type) -> None:
    model = fake_model_cls(
        final="frete calculado",
        tool_calls=[
            _tool_call(
                "calcular_frete",
                {"origem": "Sao Paulo", "destino": "Curitiba", "peso_kg": 10.0},
            )
        ],
    )
    node = build_transport_node(model, max_steps=4)
    resultado = node({"messages": [HumanMessage(content="quanto custa?")]})
    assert resultado["messages"][-1].content == "frete calculado"
    assert {tool.name for tool in model.bound_tools} == {
        "calcular_frete",
        "consultar_prazo",
        "rastrear_entrega",
        "enviar_resposta_logistica",
    }


def test_specialists_expoem_tool_comum(fake_model_cls: type) -> None:
    builders = (build_inventory_node, build_suppliers_node, build_transport_node)
    for builder in builders:
        model = fake_model_cls(final="ok")
        node = builder(model, max_steps=2)
        node({"messages": [HumanMessage(content="x")]})
        assert "enviar_resposta_logistica" in {t.name for t in model.bound_tools}


def test_specialist_stops_at_max_steps(fake_model_cls: type) -> None:
    model = fake_model_cls(
        tool_calls=[_tool_call("consultar_estoque", {"sku": "SKU-100"})] * 3
    )
    node = build_inventory_node(model, max_steps=2)
    resultado = node({"messages": [HumanMessage(content="estoque?")]})
    assert "Limite" in resultado["messages"][-1].content
    assert resultado["especialistas_visitados"] == ["estoque"]


def test_specialist_handles_unknown_tool(fake_model_cls: type) -> None:
    model = fake_model_cls(
        final="ok", tool_calls=[_tool_call("ferramenta_inexistente", {})]
    )
    node = build_transport_node(model, max_steps=2)
    resultado = node({"messages": [HumanMessage(content="x")]})
    assert resultado["messages"][-1].content == "ok"


def test_specialist_nao_encerra_com_tool_comum_em_lote(fake_model_cls: type) -> None:
    model = fake_model_cls(
        tool_calls=[
            [
                *_tool_call("consultar_estoque", {"sku": "SKU-1"}),
                {
                    "name": "enviar_resposta_logistica",
                    "args": {"resposta": "cedo", "fontes": ""},
                    "id": "call-2",
                    "type": "tool_call",
                },
            ],
            [
                {
                    "name": "enviar_resposta_logistica",
                    "args": {"resposta": "Repor", "fontes": "estoque"},
                    "id": "call-3",
                    "type": "tool_call",
                }
            ],
        ]
    )
    node = build_inventory_node(model, max_steps=4)
    resultado = node({"messages": [HumanMessage(content="estoque?")]})
    assert "Repor" in resultado["messages"][-1].content
    assert resultado["dominio"] == "estoque"


def test_specialist_encerra_com_tool_comum(fake_model_cls: type) -> None:
    model = fake_model_cls(
        tool_calls=[
            _tool_call(
                "enviar_resposta_logistica", {"resposta": "Repor", "fontes": "estoque"}
            )
        ]
    )
    node = build_inventory_node(model, max_steps=4)
    resultado = node({"messages": [HumanMessage(content="estoque?")]})
    assert "Repor" in resultado["messages"][-1].content
    assert "Fontes: estoque" in resultado["messages"][-1].content
    assert resultado["dominio"] == "estoque"
    assert resultado["especialistas_visitados"] == ["estoque"]
