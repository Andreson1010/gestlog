"""Contrato de estado compartilhado pelo grafo multiagente."""

from __future__ import annotations

from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

SpecialistName = Literal["transporte", "fornecedores", "estoque"]
Route = Literal["transporte", "fornecedores", "estoque", "FINISH"]


class AgentState(TypedDict):
    """Estado que trafega entre supervisor e especialistas.

    ``messages`` acumula o histórico (reducer ``add_messages``) e ``next`` é a
    decisão mais recente do supervisor, consumida pelas arestas condicionais.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    next: NotRequired[Route]
