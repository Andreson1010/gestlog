"""Testes do grafo multiagente."""

from __future__ import annotations

from gestlog.config import Settings
from gestlog.graph import build_graph, route_from_supervisor, run_query


def test_route_from_supervisor() -> None:
    assert route_from_supervisor({"messages": [], "next": "estoque"}) == "estoque"
    assert route_from_supervisor({"messages": [], "next": "FINISH"}) == "FINISH"
    assert route_from_supervisor({"messages": []}) == "FINISH"


def test_graph_routes_to_specialist_and_finishes(fake_model_cls: type) -> None:
    model = fake_model_cls(routes=["estoque", "FINISH"], final="há estoque suficiente")
    grafo = build_graph(model=model, settings=Settings(_env_file=None))
    resultado = run_query(grafo, "como está o SKU-100?")
    assert resultado["messages"][-1].content == "há estoque suficiente"


def test_graph_finishes_without_specialist(fake_model_cls: type) -> None:
    model = fake_model_cls(routes=["FINISH"])
    grafo = build_graph(model=model, settings=Settings(_env_file=None))
    resultado = run_query(grafo, "qual a capital da França?")
    assert resultado["messages"][-1].content == "qual a capital da França?"


def test_graph_encerra_sem_reencaminhar_apos_especialista(
    fake_model_cls: type,
) -> None:
    model = fake_model_cls(
        routes=["estoque", "estoque", "estoque"], final="resposta do especialista"
    )
    grafo = build_graph(model=model, settings=Settings(_env_file=None))
    resultado = run_query(grafo, "como está o SKU-100?")
    assert resultado["next"] == "FINISH"
    assert resultado["messages"][-1].content == "resposta do especialista"


def test_graph_encerra_quando_especialista_esgota_passos(
    fake_model_cls: type,
) -> None:
    def _chamada(id_: str) -> list[dict]:
        return [
            {
                "name": "consultar_estoque",
                "args": {"sku": "SKU-100"},
                "id": id_,
                "type": "tool_call",
            }
        ]

    model = fake_model_cls(
        routes=["estoque", "estoque"],
        tool_calls=[_chamada("c1"), _chamada("c2")],
    )
    grafo = build_graph(
        model=model, settings=Settings(_env_file=None, max_tool_steps=2)
    )
    resultado = run_query(grafo, "como está o SKU-100?")
    assert resultado["next"] == "FINISH"
    assert resultado["especialistas_visitados"] == ["estoque"]
    assert "Limite" in resultado["messages"][-1].content
