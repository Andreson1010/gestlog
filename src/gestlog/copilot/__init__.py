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
    MENSAGEM_QUOTA_EXCEDIDA,
    CopilotService,
    Recomendacao,
    Turno,
    carregar_historico,
    extrair_recomendacao,
    registrar_turno,
    texto_resposta,
)

__all__ = [
    "MENSAGEM_FORA_DE_ESCOPO",
    "MENSAGEM_INSUFICIENCIA",
    "MENSAGEM_QUOTA_EXCEDIDA",
    "CopilotService",
    "QuotaExcedida",
    "Recomendacao",
    "Turno",
    "carregar_historico",
    "check_quota",
    "extrair_recomendacao",
    "record_usage",
    "registrar_turno",
    "texto_resposta",
    "uso_no_mes",
]
