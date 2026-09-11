"""Repositório base que sempre filtra pelo tenant da sessão."""

from __future__ import annotations

from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class TenantScopedRepository(Generic[ModelT]):
    """Acesso a dados restrito a um ``tenant_id``.

    Subclasses definem o atributo de classe ``model``. Todos os métodos de
    leitura incluem o filtro de tenant, garantindo o isolamento entre clientes.
    """

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, obj: ModelT) -> ModelT:
        """Persiste um objeto e devolve-o com a sessão sincronizada."""
        self.session.add(obj)
        self.session.flush()
        return obj

    def get(self, tenant_id: UUID, obj_id: UUID) -> ModelT | None:
        """Busca um objeto pelo id, restrito ao tenant."""
        stmt = select(self.model).where(
            self.model.tenant_id == tenant_id,  # type: ignore[attr-defined]
            self.model.id == obj_id,  # type: ignore[attr-defined]
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list(self, tenant_id: UUID) -> list[ModelT]:
        """Lista os objetos do tenant."""
        stmt = select(self.model).where(
            self.model.tenant_id == tenant_id  # type: ignore[attr-defined]
        )
        return list(self.session.execute(stmt).scalars().all())
