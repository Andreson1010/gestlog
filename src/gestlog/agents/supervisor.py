"""Agente supervisor: analisa a consulta e encaminha ao especialista adequado."""

from __future__ import annotations

import logging
from collections.abc import Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, SystemMessage
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
    Se o modelo decidir reencaminhar para um especialista que já respondeu
    (presente em ``especialistas_visitados``), o nó força ``FINISH``: isso impede
    que o supervisor entre em ciclo com o mesmo especialista quando o modelo não
    sinaliza conclusão, sem bloquear o encadeamento de especialistas distintos.
    """
    router = model.with_structured_output(RouteDecision)
    system_prompt = prompt or build_supervisor_prompt()

    def node(state: AgentState) -> dict[str, Route]:
        mensagens: list[BaseMessage] = list(state.get("messages") or [])
        visitados = set(state.get("especialistas_visitados") or [])
        decision = router.invoke([SystemMessage(content=system_prompt), *mensagens])
        route: Route = (
            decision.next if isinstance(decision, RouteDecision) else "FINISH"
        )
        if route in visitados:
            logger.info("Supervisor evitou repetir %s; encerrando.", route)
            route = "FINISH"
        else:
            logger.info("Supervisor encaminhou para %s", route)
        return {"next": route}

    return node
