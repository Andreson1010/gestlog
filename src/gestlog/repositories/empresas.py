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

    def create(
        self,
        nome: str,
        retention_days: int | None = None,
        token_quota_mensal: int | None = None,
    ) -> Empresa:
        """Cria um empresa, recusando quota não positiva (erro antes do banco)."""
        if token_quota_mensal is not None and token_quota_mensal <= 0:
            raise ValueError("token_quota_mensal deve ser maior que zero.")
        empresa = Empresa(
            nome=nome,
            retention_days=retention_days,
            token_quota_mensal=token_quota_mensal,
        )
        self.session.add(empresa)
        self.session.flush()
        return empresa

    def travar(self, empresa_id: UUID) -> Empresa:
        """Carrega a linha da empresa com lock de escrita (serializa por empresa).

        O ``FOR UPDATE`` mantém o lock até o commit do chamador: dois turnos da
        MESMA empresa se serializam no check/record da quota (I-8); linhas de
        outras empresas nunca disputam o mesmo lock (EDG-02). O ``flush``
        força o round-trip do lock no dialeto que o suporta.
        """
        stmt = select(Empresa).where(Empresa.id == empresa_id).with_for_update()
        empresa = self.session.execute(stmt).scalars().one()
        self.session.flush()
        return empresa

    def get(self, empresa_id: UUID) -> Empresa | None:
        """Busca um empresa pelo id."""
        return self.session.get(Empresa, empresa_id)

    def list_all(self) -> list[Empresa]:
        """Lista todas as empresas-clientes."""
        return list(self.session.execute(select(Empresa)).scalars().all())


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
