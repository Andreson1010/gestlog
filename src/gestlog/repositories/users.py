"""Leitura de usuários para exibição de autoria na trilha de ações."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from gestlog.db.models import User


class UserRepository:
    """Consulta de identificação (e-mail) de usuários por id."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def emails(self, ids: Sequence[UUID]) -> dict[UUID, str]:
        """Mapeia os ids informados para os e-mails correspondentes.

        Ids sem usuário correspondente ficam fora do mapa; ids repetidos são
        resolvidos uma única vez.
        """
        distintos = set(ids)
        if not distintos:
            return {}
        stmt = select(User.id, User.email).where(User.id.in_(distintos))
        return {linha.id: linha.email for linha in self.session.execute(stmt)}
