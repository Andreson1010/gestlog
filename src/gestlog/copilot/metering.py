"""Medição de uso de LLM por empresa e controle de quota mensal."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from gestlog.config import Settings, get_settings
from gestlog.db.models import Empresa, UsageRecord
from gestlog.repositories.empresas import EmpresaRepository
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


def quota_da_empresa(empresa: Empresa, settings: Settings) -> int:
    """Quota da empresa; ``NULL`` cai para o teto global do settings (QUO-04)."""
    if empresa.token_quota_mensal is not None:
        return empresa.token_quota_mensal
    return settings.llm_monthly_token_quota


def travar_empresa(session: Session, empresa_id: UUID) -> Empresa:
    """Carrega a linha da empresa com lock de escrita (SQL vive no repositório)."""
    return EmpresaRepository(session).travar(empresa_id)


def record_usage(
    session: Session, empresa_id: UUID, modelo: str, tokens: int
) -> UsageRecord:
    """Registra o consumo de uma chamada ao LLM, sem confirmar a transação."""
    if tokens < 0:
        raise ValueError("tokens não pode ser negativo.")
    return UsageRepository(session).record(empresa_id, modelo, tokens)


def check_quota(
    session: Session,
    empresa: Empresa,
    settings: Settings | None = None,
    agora: datetime | None = None,
) -> int:
    """Levanta ``QuotaExcedida`` quando o uso do mês atinge a quota da empresa.

    Recebe a empresa JÁ TRAVADA (``travar_empresa``) para que check e
    ``record_usage`` aconteçam na mesma transação serializada (I-8). Usa a
    quota própria da empresa quando definida, senão o teto do Settings.
    Devolve o uso do mês quando ainda há folga, para o chamador registrar a
    telemetria sem repetir a consulta.
    """
    resolvido = settings or get_settings()
    usado = uso_no_mes(session, empresa.id, agora)
    quota = quota_da_empresa(empresa, resolvido)
    if usado >= quota:
        raise QuotaExcedida(empresa.id, usado, quota)
    return usado


def check_teto_global(session: Session, settings: Settings, agora: datetime) -> None:
    """Levanta ``QuotaExcedida`` quando o somatório de TODAS as empresas atinge o teto.

    Salvaguarda global (QUO-05): aplicada após o check por empresa, no mesmo
    fluxo do turno; o teto do Settings deixa de ser quota individual e vira
    limite do somatório mensal.
    """
    if agora.tzinfo is None:
        raise ValueError("check_teto_global exige um datetime com fuso horário.")
    total = UsageRepository(session).total_geral_desde(_inicio_do_mes(agora))
    if total >= settings.llm_monthly_token_quota:
        raise QuotaExcedida(UUID(int=0), total, settings.llm_monthly_token_quota)
