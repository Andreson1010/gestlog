"""Especialista em transporte."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from gestlog.agents.base import SpecialistNode, create_specialist_node
from gestlog.tools.transport import TOOLS

PROMPT = (
    "Você é o especialista em transporte de um sistema de gestão logística.\n"
    "Use as ferramentas para calcular fretes e prazos e para rastrear entregas.\n"
    "Se faltar um dado essencial (origem, destino, peso, código), peça ao usuário.\n"
    "Responda em português, de forma objetiva, citando os números retornados."
)


def build_transport_node(model: BaseChatModel, max_steps: int) -> SpecialistNode:
    """Constrói o nó do especialista em transporte."""
    return create_specialist_node("transporte", PROMPT, TOOLS, model, max_steps)
