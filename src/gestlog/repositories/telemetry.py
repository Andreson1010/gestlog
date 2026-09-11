"""Repositórios de uso de LLM e auditoria."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select

from gestlog.db.models import AuditLog, UsageRecord
from gestlog.repositories.base import EmpresaScopedRepository


class UsageRepository(EmpresaScopedRepository[UsageRecord]):
    """Consumo de LLM atribuído a um empresa."""

    model = UsageRecord

    def record(self, empresa_id: UUID, modelo: str, tokens: int) -> UsageRecord:
        """Registra o consumo de uma chamada ao LLM."""
        return self.add(
            UsageRecord(empresa_id=empresa_id, modelo=modelo, tokens=tokens)
        )

    def total_tokens(self, empresa_id: UUID) -> int:
        """Soma os tokens consumidos pelo empresa."""
        stmt = select(func.coalesce(func.sum(UsageRecord.tokens), 0)).where(
            UsageRecord.empresa_id == empresa_id
        )
        return int(self.session.execute(stmt).scalar_one())


class AuditRepository(EmpresaScopedRepository[AuditLog]):
    """Eventos de auditoria por empresa."""

    model = AuditLog

    def record(
        self,
        empresa_id: UUID,
        evento: str,
        user_id: UUID | None = None,
        detalhe: dict | None = None,
    ) -> AuditLog:
        """Registra um evento de auditoria."""
        return self.add(
            AuditLog(
                empresa_id=empresa_id,
                user_id=user_id,
                evento=evento,
                detalhe=detalhe,
            )
        )
