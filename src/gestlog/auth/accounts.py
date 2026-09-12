"""Casos de uso de conta: onboarding da empresa e convite de usuários."""

from __future__ import annotations

from uuid import UUID

from fastapi_users.schemas import BaseUserCreate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gestlog.auth.manager import UserManager
from gestlog.db.models import Empresa, Membership, User


async def criar_conta(
    session: AsyncSession,
    user_manager: UserManager,
    nome_empresa: str,
    email: str,
    senha: str,
) -> tuple[Empresa, User]:
    """Cria a empresa e torna o usuário fundador seu administrador."""
    usuario = await user_manager.create(
        BaseUserCreate(email=email, password=senha), safe=False
    )
    empresa = Empresa(nome=nome_empresa)
    session.add(empresa)
    await session.flush()
    session.add(Membership(user_id=usuario.id, empresa_id=empresa.id, papel="admin"))
    await session.commit()
    return empresa, usuario


async def convidar_usuario(
    session: AsyncSession,
    user_manager: UserManager,
    empresa_id: UUID,
    email: str,
    papel: str,
    senha: str,
) -> Membership:
    """Vincula um usuário à empresa (criando-o se ainda não existir)."""
    usuario = (
        (await session.execute(select(User).where(User.email == email)))
        .scalars()
        .first()
    )
    if usuario is None:
        usuario = await user_manager.create(
            BaseUserCreate(email=email, password=senha), safe=False
        )
    vinculo = Membership(user_id=usuario.id, empresa_id=empresa_id, papel=papel)
    session.add(vinculo)
    await session.commit()
    return vinculo
