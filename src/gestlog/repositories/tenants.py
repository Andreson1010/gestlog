"""Repositórios de tenants e vínculos de usuários."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from gestlog.db.models import Membership, Tenant
from gestlog.repositories.base import TenantScopedRepository


class TenantRepository:
    """Criação e leitura de empresas-clientes."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, nome: str, retention_days: int | None = None) -> Tenant:
        """Cria um tenant."""
        tenant = Tenant(nome=nome, retention_days=retention_days)
        self.session.add(tenant)
        self.session.flush()
        return tenant

    def get(self, tenant_id: UUID) -> Tenant | None:
        """Busca um tenant pelo id."""
        return self.session.get(Tenant, tenant_id)


class MembershipRepository(TenantScopedRepository[Membership]):
    """Vínculos de usuários aos tenants."""

    model = Membership

    def add_member(
        self, tenant_id: UUID, user_id: UUID, papel: str = "operador"
    ) -> Membership:
        """Vincula um usuário a um tenant com o papel informado."""
        return self.add(Membership(tenant_id=tenant_id, user_id=user_id, papel=papel))

    def by_user(self, user_id: UUID) -> list[Membership]:
        """Lista os vínculos de um usuário (todos os tenants)."""
        stmt = select(Membership).where(Membership.user_id == user_id)
        return list(self.session.execute(stmt).scalars().all())
