"""Configuração central do sistema (fonte única via variáveis de ambiente)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SEGREDO_DEV = "dev-secret-change-me"
TAMANHO_MINIMO_SEGREDO = 32


class Settings(BaseSettings):
    """Configuração do sistema carregada do ambiente e/ou arquivo ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    llm_model: str = "qwen2.5:7b"
    supervisor_model: str = ""
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)

    max_tool_steps: int = Field(default=6, gt=0, le=20)
    recursion_limit: int = Field(default=25, gt=0)
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://gestlog:gestlog@localhost:5432/gestlog"
    ambiente: Literal["dev", "prod"] = "dev"
    auth_secret: str = SEGREDO_DEV
    auth_cookie_name: str = "gestlog_auth"
    auth_cookie_secure: bool = True
    session_expire_minutes: int = Field(default=1440, gt=0)
    default_retention_days: int = Field(default=365, gt=0)
    llm_monthly_token_quota: int = Field(default=1_000_000, gt=0)

    @model_validator(mode="after")
    def _validar_segredo(self) -> Settings:
        """Impede segredo de desenvolvimento/curto quando ``ambiente`` é prod."""
        if self.ambiente != "prod":
            return self
        if self.auth_secret == SEGREDO_DEV:
            raise ValueError("AUTH_SECRET deve ser definido quando AMBIENTE=prod.")
        if len(self.auth_secret) < TAMANHO_MINIMO_SEGREDO:
            raise ValueError(
                f"AUTH_SECRET deve ter ao menos {TAMANHO_MINIMO_SEGREDO} caracteres."
            )
        return self

    @property
    def supervisor_llm_model(self) -> str:
        """Modelo do supervisor; cai para ``llm_model`` quando não definido."""
        return self.supervisor_model or self.llm_model


@lru_cache
def get_settings() -> Settings:
    """Retorna (e memoiza) a configuração do processo."""
    return Settings()
