"""Especialista em fornecedores."""

from __future__ import annotations

from collections.abc import Sequence

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

from gestlog.agents.base import SpecialistNode, create_specialist_node
from gestlog.tools.common import COMMON_TOOLS
from gestlog.tools.suppliers import TOOLS

PROMPT = (
    "Você é o especialista em fornecedores de um sistema de gestão logística.\n"
    "Use as ferramentas para listar, consultar e avaliar fornecedores.\n"
    "Ao recomendar um fornecedor, cite nota, prazo e histórico de atrasos.\n"
    "Responda em português, de forma objetiva."
)


def build_suppliers_node(
    model: BaseChatModel,
    max_steps: int,
    tools: Sequence[BaseTool] | None = None,
) -> SpecialistNode:
    """Constrói o nó do especialista em fornecedores.

    ``tools`` permite injetar as ferramentas do tenant; quando omitido, usa o
    mock determinístico como andaime. A tool comum é sempre anexada.
    """
    base = TOOLS if tools is None else tools
    return create_specialist_node(
        "fornecedores", PROMPT, [*base, *COMMON_TOOLS], model, max_steps
    )
