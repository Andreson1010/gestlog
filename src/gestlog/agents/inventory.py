"""Especialista em estoque."""

from __future__ import annotations

from collections.abc import Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

from gestlog.agents.base import SpecialistNode, create_specialist_node
from gestlog.tools.common import COMMON_TOOLS, INSTRUCAO_RESPOSTA
from gestlog.tools.inventory import TOOLS

PROMPT = (
    "Você é o especialista em estoque de um sistema de gestão logística.\n"
    "Use as ferramentas para consultar níveis, movimentações e sugerir reposição.\n"
    "Alerte quando a quantidade estiver abaixo do mínimo.\n"
    f"{INSTRUCAO_RESPOSTA}\n"
    "Responda em português, de forma objetiva."
)


def build_inventory_node(
    model: BaseChatModel,
    max_steps: int,
    tools: Sequence[BaseTool] | None = None,
) -> SpecialistNode:
    """Constrói o nó do especialista em estoque.

    ``tools`` permite injetar as ferramentas do tenant; quando omitido, usa o
    mock determinístico como andaime. A tool comum é sempre anexada.
    """
    base = TOOLS if tools is None else tools
    return create_specialist_node(
        "estoque", PROMPT, [*base, *COMMON_TOOLS], model, max_steps
    )
