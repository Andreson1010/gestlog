"""Repositório base que sempre filtra pelo empresa da sessão."""

from __future__ import annotations

from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class EmpresaScopedRepository(Generic[ModelT]):
    """Acesso a dados restrito a um ``empresa_id``.

    Subclasses definem o atributo de classe ``model``. Todos os métodos de
    leitura incluem o filtro de empresa, garantindo o isolamento entre clientes.
    """

    model: type[ModelT]

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, obj: ModelT) -> ModelT:
        """Persiste um objeto e devolve-o com a sessão sincronizada."""
        self.session.add(obj)
        self.session.flush()
        return obj

    def get(self, empresa_id: UUID, obj_id: UUID) -> ModelT | None:
        """Busca um objeto pelo id, restrito ao empresa."""
        stmt = select(self.model).where(
            self.model.empresa_id == empresa_id,  # type: ignore[attr-defined]
            self.model.id == obj_id,  # type: ignore[attr-defined]
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list(self, empresa_id: UUID) -> list[ModelT]:
        """Lista os objetos do empresa."""
        stmt = select(self.model).where(
            self.model.empresa_id == empresa_id  # type: ignore[attr-defined]
        )
        return list(self.session.execute(stmt).scalars().all())
