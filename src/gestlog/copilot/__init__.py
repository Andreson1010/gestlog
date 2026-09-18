"""Serviço de copiloto do gestlog."""

from __future__ import annotations

from gestlog.copilot.metering import (
    QuotaExcedida,
    check_quota,
    record_usage,
    uso_no_mes,
)
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
    "QuotaExcedida",
    "Recomendacao",
    "Turno",
    "carregar_historico",
    "check_quota",
    "extrair_recomendacao",
    "record_usage",
    "registrar_turno",
    "uso_no_mes",
]
