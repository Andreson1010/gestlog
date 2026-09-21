"""Contrato de estado compartilhado pelo grafo multiagente."""

from __future__ import annotations

import operator
from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

SpecialistName = Literal["transporte", "fornecedores", "estoque"]
Route = Literal["transporte", "fornecedores", "estoque", "FINISH"]


class AgentState(TypedDict):
    """Estado que trafega entre supervisor e especialistas.

    ``messages`` acumula o histórico (reducer ``add_messages``) e ``next`` é a
    decisão mais recente do supervisor, consumida pelas arestas condicionais.
    ``dominio`` registra qual especialista encerrou a resposta com a ferramenta
    comum, permitindo ao copiloto estruturar a recomendação (T21).
    ``tokens_usados`` soma (reducer ``operator.add``) os tokens reportados pelos
    especialistas, base da medição de uso da T27/T28.
    ``especialistas_visitados`` acumula (reducer ``operator.add``) os domínios já
    executados, para o supervisor não reencaminhar em ciclo ao mesmo especialista.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    next: NotRequired[Route]
    dominio: NotRequired[str]
    tokens_usados: NotRequired[Annotated[int, operator.add]]
    especialistas_visitados: NotRequired[Annotated[list[SpecialistName], operator.add]]
