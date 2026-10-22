"""Apoio comum dos testes: pais persistidos para as FKs reais.

O SQLite não aplica chaves estrangeiras por padrão, mas o Postgres da matriz de
dialetos (``GESTLOG_TEST_DATABASE_URL``) aplica — e a produção é Postgres. Testes
que referenciam ``user.id``/``empresa.id`` devem semear o pai de verdade.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from gestlog.db.models import User
from gestlog.repositories.empresas import EmpresaRepository


def criar_usuario(session: Session) -> UUID:
    """Persiste um usuário de teste e devolve o id (pai das FKs de ``user.id``).

    O ``commit`` protege o usuário dos ``rollback`` internos dos serviços (no
    modo savepoint do Postgres eles desfariam a inserção ainda pendente).
    """
    usuario = User(
        email=f"{uuid4().hex}@teste.local",
        hashed_password="hash-de-teste",
        is_active=True,
        is_superuser=False,
        is_verified=True,
    )
    session.add(usuario)
    session.commit()
    return usuario.id


def criar_empresa(
    session: Session, nome: str = "A", retention_days: int | None = None
) -> UUID:
    """Persiste uma empresa de teste e devolve o id (pai das FKs de ``empresa.id``)."""
    empresa = EmpresaRepository(session).create(nome, retention_days)
    session.commit()
    return empresa.id
