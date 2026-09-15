"""Especialista em estoque."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from gestlog.agents.base import SpecialistNode, create_specialist_node
from gestlog.tools.common import COMMON_TOOLS
from gestlog.tools.inventory import TOOLS

PROMPT = (
    "Você é o especialista em estoque de um sistema de gestão logística.\n"
    "Use as ferramentas para consultar níveis, movimentações e sugerir reposição.\n"
    "Alerte quando a quantidade estiver abaixo do mínimo.\n"
    "Responda em português, de forma objetiva."
)


def build_inventory_node(model: BaseChatModel, max_steps: int) -> SpecialistNode:
    """Constrói o nó do especialista em estoque."""
    return create_specialist_node(
        "estoque", PROMPT, [*TOOLS, *COMMON_TOOLS], model, max_steps
    )
