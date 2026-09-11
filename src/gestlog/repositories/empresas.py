"""Repositórios de empresas e vínculos de usuários."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from gestlog.db.models import Empresa, Membership
from gestlog.repositories.base import EmpresaScopedRepository


class EmpresaRepository:
    """Criação e leitura de empresas-clientes."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, nome: str, retention_days: int | None = None) -> Empresa:
        """Cria um empresa."""
        empresa = Empresa(nome=nome, retention_days=retention_days)
        self.session.add(empresa)
        self.session.flush()
        return empresa

    def get(self, empresa_id: UUID) -> Empresa | None:
        """Busca um empresa pelo id."""
        return self.session.get(Empresa, empresa_id)


class MembershipRepository(EmpresaScopedRepository[Membership]):
    """Vínculos de usuários aos empresas."""

    model = Membership

    def add_member(
        self, empresa_id: UUID, user_id: UUID, papel: str = "operador"
    ) -> Membership:
        """Vincula um usuário a um empresa com o papel informado."""
        return self.add(Membership(empresa_id=empresa_id, user_id=user_id, papel=papel))

    def by_user(self, user_id: UUID) -> list[Membership]:
        """Lista os vínculos de um usuário (todos os empresas)."""
        stmt = select(Membership).where(Membership.user_id == user_id)
        return list(self.session.execute(stmt).scalars().all())
