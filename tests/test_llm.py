"""Testes da fábrica de modelos."""

from __future__ import annotations

from gestlog.config import Settings
from gestlog.llm import build_chat_model


def test_build_chat_model_uses_settings() -> None:
    settings = Settings(
        _env_file=None,
        llm_model="meu-modelo",
        llm_base_url="http://localhost:9999/v1",
    )
    model = build_chat_model(settings=settings)
    assert model.model_name == "meu-modelo"
