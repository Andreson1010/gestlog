"""Repositórios de uso de LLM e auditoria."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select

from gestlog.db.models import AuditLog, UsageRecord
from gestlog.repositories.base import TenantScopedRepository


class UsageRepository(TenantScopedRepository[UsageRecord]):
    """Consumo de LLM atribuído a um tenant."""

    model = UsageRecord

    def record(self, tenant_id: UUID, modelo: str, tokens: int) -> UsageRecord:
        """Registra o consumo de uma chamada ao LLM."""
        return self.add(UsageRecord(tenant_id=tenant_id, modelo=modelo, tokens=tokens))

    def total_tokens(self, tenant_id: UUID) -> int:
        """Soma os tokens consumidos pelo tenant."""
        stmt = select(func.coalesce(func.sum(UsageRecord.tokens), 0)).where(
            UsageRecord.tenant_id == tenant_id
        )
        return int(self.session.execute(stmt).scalar_one())


class AuditRepository(TenantScopedRepository[AuditLog]):
    """Eventos de auditoria por tenant."""

    model = AuditLog

    def record(
        self,
        tenant_id: UUID,
        evento: str,
        user_id: UUID | None = None,
        detalhe: dict | None = None,
    ) -> AuditLog:
        """Registra um evento de auditoria."""
        return self.add(
            AuditLog(
                tenant_id=tenant_id,
                user_id=user_id,
                evento=evento,
                detalhe=detalhe,
            )
        )
