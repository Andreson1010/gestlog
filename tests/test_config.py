"""Testes de configuração."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from gestlog.config import Settings, get_settings


def test_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.llm_base_url.startswith("http")
    assert settings.max_tool_steps == 6
    assert settings.recursion_limit == 25
    assert settings.supervisor_llm_model == settings.llm_model


def test_mvp_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.database_url.startswith("postgresql")
    assert settings.auth_secret
    assert settings.session_expire_minutes > 0
    assert settings.default_retention_days > 0
    assert settings.llm_monthly_token_quota > 0


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    settings = Settings(_env_file=None)
    assert settings.database_url == "sqlite+pysqlite:///:memory:"


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("session_expire_minutes", 0),
        ("default_retention_days", 0),
        ("llm_monthly_token_quota", -1),
    ],
)
def test_valores_positivos_obrigatorios(campo: str, valor: int) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{campo: valor})


def test_dev_aceita_segredo_padrao() -> None:
    settings = Settings(_env_file=None)
    assert settings.ambiente == "dev"
    assert settings.auth_secret == "dev-secret-change-me"


def test_prod_rejeita_segredo_de_dev() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ambiente="prod")


def test_prod_rejeita_segredo_curto() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ambiente="prod", auth_secret="curto")


def test_prod_aceita_segredo_forte() -> None:
    segredo = "s" * 40
    settings = Settings(_env_file=None, ambiente="prod", auth_secret=segredo)
    assert settings.auth_secret == segredo


def test_supervisor_model_override() -> None:
    settings = Settings(_env_file=None, supervisor_model="llama3.1")
    assert settings.supervisor_llm_model == "llama3.1"


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
