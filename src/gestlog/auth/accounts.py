"""Casos de uso de conta: onboarding da empresa e convite de usuários."""

from __future__ import annotations

from uuid import UUID

from fastapi_users import exceptions
from fastapi_users.password import PasswordHelper
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gestlog.db.models import Empresa, Membership, User

_password_helper = PasswordHelper()


async def _por_email(session: AsyncSession, email: str) -> User | None:
    """Busca um usuário pelo e-mail (sem escopo de empresa)."""
    stmt = select(User).where(User.email == email)
    return (await session.execute(stmt)).scalars().first()


def _novo_usuario(email: str, senha: str) -> User:
    """Constrói um usuário ativo e verificado com a senha já hasheada."""
    return User(
        email=email,
        hashed_password=_password_helper.hash(senha),
        is_active=True,
        is_verified=True,
    )


async def criar_conta(
    session: AsyncSession,
    nome_empresa: str,
    email: str,
    senha: str,
) -> tuple[Empresa, User]:
    """Cria empresa e usuário fundador (admin) numa única transação.

    A empresa, o usuário e o vínculo são persistidos no mesmo ``commit`` para
    não deixar usuário órfão se a gravação do vínculo falhar.
    """
    if await _por_email(session, email) is not None:
        raise exceptions.UserAlreadyExists(email)
    empresa = Empresa(nome=nome_empresa)
    usuario = _novo_usuario(email, senha)
    session.add_all([empresa, usuario])
    await session.flush()
    session.add(Membership(user_id=usuario.id, empresa_id=empresa.id, papel="admin"))
    await session.commit()
    return empresa, usuario


async def convidar_usuario(
    session: AsyncSession,
    empresa_id: UUID,
    email: str,
    papel: str,
    senha: str,
) -> Membership:
    """Vincula um usuário à empresa, criando-o numa única transação se preciso."""
    usuario = await _por_email(session, email)
    if usuario is None:
        usuario = _novo_usuario(email, senha)
        session.add(usuario)
        await session.flush()
    vinculo = Membership(user_id=usuario.id, empresa_id=empresa_id, papel=papel)
    session.add(vinculo)
    await session.commit()
    return vinculo
