"""Agente supervisor: analisa a consulta e encaminha ao especialista adequado."""

from __future__ import annotations

import logging
from collections.abc import Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from pydantic import BaseModel, Field

from gestlog.state import AgentState, Route, SpecialistName

logger = logging.getLogger(__name__)

SPECIALIST_DESCRIPTIONS: dict[SpecialistName, str] = {
    "transporte": "fretes, prazos de entrega, rastreamento e ocorrências de transporte",
    "fornecedores": "cadastro, avaliação, negociação e desempenho de fornecedores",
    "estoque": "níveis de estoque, reposição, movimentações e inventário",
}


class RouteDecision(BaseModel):
    """Decisão de roteamento tomada pelo supervisor."""

    next: Route = Field(description="Próximo destino da consulta.")
    reasoning: str = Field(default="", description="Justificativa curta da decisão.")


SupervisorNode = Callable[[AgentState], dict[str, Route]]


def build_supervisor_prompt() -> str:
    """Monta o prompt do supervisor a partir dos especialistas registrados."""
    opcoes = "\n".join(
        f"- {nome}: {descricao}" for nome, descricao in SPECIALIST_DESCRIPTIONS.items()
    )
    return (
        "Você é o agente supervisor de um sistema de gestão logística.\n"
        "Analise a solicitação do usuário e encaminhe para o especialista adequado.\n"
        f"Especialistas disponíveis:\n{opcoes}\n"
        "- FINISH: use quando a solicitação já foi respondida ou está fora do escopo.\n"
        "Encaminhe para no máximo um especialista por vez."
    )


def create_supervisor_node(
    model: BaseChatModel,
    prompt: str | None = None,
) -> SupervisorNode:
    """Cria o nó de roteamento usando saída estruturada (``RouteDecision``).

    O modelo configurado precisa suportar structured output / function calling.
    """
    router = model.with_structured_output(RouteDecision)
    system_prompt = prompt or build_supervisor_prompt()

    def node(state: AgentState) -> dict[str, Route]:
        decision = router.invoke(
            [SystemMessage(content=system_prompt), *state["messages"]]
        )
        route: Route = (
            decision.next if isinstance(decision, RouteDecision) else "FINISH"
        )
        logger.info("Supervisor encaminhou para %s", route)
        return {"next": route}

    return node
