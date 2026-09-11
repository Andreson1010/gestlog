"""Montagem e execução do grafo multiagente."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from gestlog.agents.inventory import build_inventory_node
from gestlog.agents.supervisor import create_supervisor_node
from gestlog.agents.suppliers import build_suppliers_node
from gestlog.agents.transport import build_transport_node
from gestlog.config import Settings, get_settings
from gestlog.llm import build_chat_model
from gestlog.state import AgentState, Route

SPECIALISTS = ("transporte", "fornecedores", "estoque")


def route_from_supervisor(state: AgentState) -> Route:
    """Aresta condicional: traduz ``state["next"]`` na rota do grafo."""
    destino = state.get("next", "FINISH")
    return destino if destino in SPECIALISTS else "FINISH"


def build_graph(
    model: BaseChatModel | None = None,
    settings: Settings | None = None,
) -> CompiledStateGraph:
    """Compila o grafo supervisor + especialistas.

    ``model`` é injetável para testes; em produção é criado a partir do ``.env``.
    """
    resolved = settings or get_settings()
    specialist_model = model or build_chat_model(settings=resolved)
    supervisor_model = (
        specialist_model
        if not resolved.supervisor_model
        else build_chat_model(resolved.supervisor_llm_model, settings=resolved)
    )

    builder = StateGraph(AgentState)
    builder.add_node("supervisor", create_supervisor_node(supervisor_model))
    builder.add_node(
        "transporte", build_transport_node(specialist_model, resolved.max_tool_steps)
    )
    builder.add_node(
        "fornecedores", build_suppliers_node(specialist_model, resolved.max_tool_steps)
    )
    builder.add_node(
        "estoque", build_inventory_node(specialist_model, resolved.max_tool_steps)
    )

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "transporte": "transporte",
            "fornecedores": "fornecedores",
            "estoque": "estoque",
            "FINISH": END,
        },
    )
    for especialista in SPECIALISTS:
        builder.add_edge(especialista, "supervisor")

    return builder.compile()


def run_query(
    graph: CompiledStateGraph,
    question: str,
    recursion_limit: int = 25,
) -> dict:
    """Executa uma pergunta no grafo e retorna o estado final."""
    return graph.invoke(
        {"messages": [HumanMessage(content=question)]},
        config={"recursion_limit": recursion_limit},
    )
