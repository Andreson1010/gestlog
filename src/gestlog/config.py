"""Configuração central do sistema (fonte única via variáveis de ambiente)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @property
    def supervisor_llm_model(self) -> str:
        """Modelo do supervisor; cai para ``llm_model`` quando não definido."""
        return self.supervisor_model or self.llm_model


@lru_cache
def get_settings() -> Settings:
    """Retorna (e memoiza) a configuração do processo."""
    return Settings()
