"""Testes de configuração."""

from __future__ import annotations

from gestlog.config import Settings, get_settings


def test_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.llm_base_url.startswith("http")
    assert settings.max_tool_steps == 6
    assert settings.recursion_limit == 25
    assert settings.supervisor_llm_model == settings.llm_model


def test_supervisor_model_override() -> None:
    settings = Settings(_env_file=None, supervisor_model="llama3.1")
    assert settings.supervisor_llm_model == "llama3.1"


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
