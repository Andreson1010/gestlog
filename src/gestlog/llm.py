"""Fábrica de modelos de chat apontados para um endpoint compatível com OpenAI."""

from __future__ import annotations

from langchain_openai import ChatOpenAI

from gestlog.config import Settings, get_settings


def build_chat_model(
    model: str | None = None,
    settings: Settings | None = None,
) -> ChatOpenAI:
    """Cria um ``ChatOpenAI`` configurado para o endpoint do ``.env``."""
    resolved = settings or get_settings()
    return ChatOpenAI(
        model=model or resolved.llm_model,
        base_url=resolved.llm_base_url,
        api_key=resolved.llm_api_key,
        temperature=resolved.llm_temperature,
    )
