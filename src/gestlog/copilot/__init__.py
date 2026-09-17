"""Serviço de copiloto do gestlog."""

from __future__ import annotations

from gestlog.copilot.service import (
    MENSAGEM_FORA_DE_ESCOPO,
    CopilotService,
    Turno,
    carregar_historico,
    registrar_turno,
)

__all__ = [
    "MENSAGEM_FORA_DE_ESCOPO",
    "CopilotService",
    "Turno",
    "carregar_historico",
    "registrar_turno",
]
