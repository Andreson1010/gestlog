"""Serviço de copiloto do gestlog."""

from __future__ import annotations

from gestlog.copilot.service import (
    MENSAGEM_FORA_DE_ESCOPO,
    MENSAGEM_INSUFICIENCIA,
    CopilotService,
    Recomendacao,
    Turno,
    carregar_historico,
    extrair_recomendacao,
    registrar_turno,
)

__all__ = [
    "MENSAGEM_FORA_DE_ESCOPO",
    "MENSAGEM_INSUFICIENCIA",
    "CopilotService",
    "Recomendacao",
    "Turno",
    "carregar_historico",
    "extrair_recomendacao",
    "registrar_turno",
]
