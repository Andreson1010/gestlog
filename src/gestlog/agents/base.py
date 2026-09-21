"""Infraestrutura compartilhada dos agentes especialistas."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from gestlog.state import AgentState, SpecialistName
from gestlog.tools.common import NOME_TOOL_RESPOSTA

logger = logging.getLogger(__name__)


class SpecialistOutput(TypedDict, total=False):
    """Fragmento que o nó especialista devolve ao estado do grafo."""

    messages: list[BaseMessage]
    dominio: str
    tokens_usados: int
    especialistas_visitados: list[SpecialistName]


SpecialistNode = Callable[[AgentState], SpecialistOutput]


def _tokens_da_resposta(response: BaseMessage) -> int:
    """Soma os tokens reportados pelo modelo na resposta, quando houver."""
    uso = getattr(response, "usage_metadata", None)
    if not isinstance(uso, Mapping):
        return 0
    return int(uso.get("total_tokens") or 0)


def _fragmento(
    name: SpecialistName,
    messages: list[BaseMessage],
    tokens: int,
    dominio: str | None = None,
) -> SpecialistOutput:
    """Monta o fragmento devolvido ao grafo, registrando o domínio visitado."""
    fragmento: SpecialistOutput = {
        "messages": messages,
        "tokens_usados": tokens,
        "especialistas_visitados": [name],
    }
    if dominio is not None:
        fragmento["dominio"] = dominio
    return fragmento


def create_specialist_node(
    name: SpecialistName,
    system_prompt: str,
    tools: Sequence[BaseTool],
    model: BaseChatModel,
    max_steps: int,
) -> SpecialistNode:
    """Cria um nó ReAct que executa um loop de tool calling com limite de passos.

    O nó devolve apenas a resposta final ao estado pai, evitando poluir o
    histórico do supervisor com mensagens intermediárias de ferramenta, e
    acumula em ``tokens_usados`` o uso reportado pelas chamadas ao modelo.
    """
    model_with_tools = model.bind_tools(list(tools))
    tools_by_name = {tool.name: tool for tool in tools}

    def node(state: AgentState) -> SpecialistOutput:
        messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt),
            *state["messages"],
        ]
        tokens = 0
        for _ in range(max_steps):
            response = model_with_tools.invoke(messages)
            tokens += _tokens_da_resposta(response)
            if not isinstance(response, AIMessage) or not response.tool_calls:
                return _fragmento(name, [response], tokens)
            terminal = None
            if len(response.tool_calls) == 1:
                chamada = response.tool_calls[0]
                if (
                    chamada["name"] == NOME_TOOL_RESPOSTA
                    and chamada["name"] in tools_by_name
                ):
                    terminal = chamada
            if terminal is not None:
                result = tools_by_name[terminal["name"]].invoke(terminal["args"])
                return _fragmento(name, [AIMessage(content=str(result))], tokens, name)
            messages.append(response)
            for call in response.tool_calls:
                tool = tools_by_name.get(call["name"])
                result = (
                    tool.invoke(call["args"])
                    if tool is not None
                    else f"Ferramenta desconhecida: {call['name']}"
                )
                messages.append(
                    ToolMessage(content=str(result), tool_call_id=call["id"])
                )
        logger.warning(
            "%s atingiu o limite de %d passos de ferramenta", name, max_steps
        )
        return _fragmento(
            name,
            [AIMessage(content=f"[{name}] Limite de ferramentas atingido.")],
            tokens,
        )

    return node
