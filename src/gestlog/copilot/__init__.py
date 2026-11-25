"""Serviço de copiloto do gestlog."""

from __future__ import annotations

from gestlog.copilot.metering import (
    QuotaExcedida,
    check_quota,
    check_teto_global,
    quota_da_empresa,
    record_usage,
    travar_empresa,
    uso_no_mes,
)
from gestlog.copilot.service import (
    MENSAGEM_ERRO_COPILOTO,
    MENSAGEM_FORA_DE_ESCOPO,
    MENSAGEM_INSUFICIENCIA,
    MENSAGEM_QUOTA_EXCEDIDA,
    CopilotService,
    Recomendacao,
    Turno,
    carregar_historico,
    extrair_recomendacao,
    registrar_turno,
    texto_principal,
    texto_resposta,
)

__all__ = [
    "MENSAGEM_ERRO_COPILOTO",
    "MENSAGEM_FORA_DE_ESCOPO",
    "MENSAGEM_INSUFICIENCIA",
    "MENSAGEM_QUOTA_EXCEDIDA",
    "CopilotService",
    "QuotaExcedida",
    "Recomendacao",
    "Turno",
    "carregar_historico",
    "check_quota",
    "check_teto_global",
    "extrair_recomendacao",
    "quota_da_empresa",
    "record_usage",
    "registrar_turno",
    "texto_principal",
    "texto_resposta",
    "travar_empresa",
    "uso_no_mes",
]
