"""Medição de uso de LLM por empresa e controle de quota mensal."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from gestlog.config import Settings, get_settings
from gestlog.db.models import UsageRecord
from gestlog.repositories.telemetry import UsageRepository


class QuotaExcedida(Exception):
    """Erro levantado quando o uso do mês atinge a quota da empresa."""

    def __init__(self, empresa_id: UUID, usado: int, quota: int) -> None:
        super().__init__(
            f"Quota de {quota} tokens atingida para a empresa {empresa_id} "
            f"(usado: {usado})."
        )
        self.empresa_id = empresa_id
        self.usado = usado
        self.quota = quota


def _inicio_do_mes(agora: datetime) -> datetime:
    """Primeiro instante do mês de ``agora``, preservando o fuso."""
    return agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def uso_no_mes(
    session: Session, empresa_id: UUID, agora: datetime | None = None
) -> int:
    """Soma os tokens consumidos pela empresa no mês corrente."""
    momento = agora or datetime.now(UTC)
    if momento.tzinfo is None:
        raise ValueError("uso_no_mes exige um datetime com fuso horário.")
    return UsageRepository(session).total_tokens_desde(
        empresa_id, _inicio_do_mes(momento)
    )


def record_usage(
    session: Session, empresa_id: UUID, modelo: str, tokens: int
) -> UsageRecord:
    """Registra o consumo de uma chamada ao LLM, sem confirmar a transação."""
    if tokens < 0:
        raise ValueError("tokens não pode ser negativo.")
    return UsageRepository(session).record(empresa_id, modelo, tokens)


def check_quota(
    session: Session,
    empresa_id: UUID,
    settings: Settings | None = None,
    agora: datetime | None = None,
) -> int:
    """Levanta ``QuotaExcedida`` quando o uso do mês atinge a quota.

    Devolve o uso do mês quando ainda há folga, para o chamador registrar a
    telemetria sem repetir a consulta.
    """
    resolvido = settings or get_settings()
    usado = uso_no_mes(session, empresa_id, agora)
    if usado >= resolvido.llm_monthly_token_quota:
        raise QuotaExcedida(empresa_id, usado, resolvido.llm_monthly_token_quota)
    return usado
