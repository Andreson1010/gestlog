"""Infraestrutura compartilhada dos agentes especialistas."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from gestlog.state import AgentState, SpecialistName

logger = logging.getLogger(__name__)

SpecialistNode = Callable[[AgentState], dict[str, list[BaseMessage]]]


def create_specialist_node(
    name: SpecialistName,
    system_prompt: str,
    tools: Sequence[BaseTool],
    model: BaseChatModel,
    max_steps: int,
) -> SpecialistNode:
    """Cria um nó ReAct que executa um loop de tool calling com limite de passos.

    O nó devolve apenas a resposta final ao estado pai, evitando poluir o
    histórico do supervisor com mensagens intermediárias de ferramenta.
    """
    model_with_tools = model.bind_tools(list(tools))
    tools_by_name = {tool.name: tool for tool in tools}

    def node(state: AgentState) -> dict[str, list[BaseMessage]]:
        messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt),
            *state["messages"],
        ]
        for _ in range(max_steps):
            response = model_with_tools.invoke(messages)
            if not isinstance(response, AIMessage) or not response.tool_calls:
                return {"messages": [response]}
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
        return {
            "messages": [AIMessage(content=f"[{name}] Limite de ferramentas atingido.")]
        }

    return node
