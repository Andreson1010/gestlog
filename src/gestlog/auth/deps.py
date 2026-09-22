"""Dependências de usuário autenticado e resolução da empresa (tenancy).

O auth é a única camada com acesso assíncrono ao banco (AD-013), por isso a
resolução de vínculo/empresa é feita aqui, sobre ``AsyncSession``.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi_users.authentication import Authenticator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gestlog.auth.backend import build_auth_backend
from gestlog.auth.db import get_async_session
from gestlog.auth.manager import get_user_manager
from gestlog.config import get_settings
from gestlog.db.models import Empresa, Membership, User

auth_backend = build_auth_backend(get_settings())
authenticator = Authenticator([auth_backend], get_user_manager)
current_active_user = authenticator.current_user(active=True)
current_active_user_optional = authenticator.current_user(active=True, optional=True)


async def get_current_user(
    user: Annotated[User, Depends(current_active_user)],
) -> User:
    """Devolve o usuário autenticado (401 se não houver sessão válida)."""
    return user


async def _buscar_membership(session: AsyncSession, user_id: UUID) -> Membership | None:
    """Busca o vínculo mais antigo do usuário, de forma determinística."""
    stmt = (
        select(Membership)
        .where(Membership.user_id == user_id)
        .order_by(Membership.created_at, Membership.id)
    )
    return (await session.execute(stmt)).scalars().first()


async def get_current_membership(
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Membership:
    """Resolve o vínculo do usuário com a empresa (403 se não houver).

    O MVP assume um vínculo por usuário; se houver mais de um, usa o mais
    antigo de forma determinística. Seleção de empresa ativa fica para depois.
    """
    membership = await _buscar_membership(session, user.id)
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário sem empresa vinculada.",
        )
    return membership


async def get_current_empresa(
    membership: Annotated[Membership, Depends(get_current_membership)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Empresa:
    """Devolve a empresa da sessão a partir do vínculo do usuário."""
    empresa = await session.get(Empresa, membership.empresa_id)
    if empresa is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário sem empresa vinculada.",
        )
    return empresa


async def get_current_membership_optional(
    user: Annotated[User | None, Depends(current_active_user_optional)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Membership | None:
    """Devolve o vínculo do usuário, ou ``None`` sem usuário/empresa.

    Usado por páginas que decidem o que exibir conforme o papel, sem exigir
    um papel específico.
    """
    if user is None:
        return None
    return await _buscar_membership(session, user.id)


async def get_current_empresa_optional(
    user: Annotated[User | None, Depends(current_active_user_optional)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Empresa | None:
    """Devolve a empresa da sessão, ou ``None`` sem usuário/vínculo.

    Usado por páginas que decidem o redirect de login por conta própria.
    """
    if user is None:
        return None
    membership = await _buscar_membership(session, user.id)
    if membership is None:
        return None
    return await session.get(Empresa, membership.empresa_id)


async def verificar_empresa_do_recurso(
    empresa_id: UUID,
    empresa: Annotated[Empresa, Depends(get_current_empresa)],
) -> Empresa:
    """Garante que o recurso pertence à empresa da sessão (senão 404)."""
    if empresa.id != empresa_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Não encontrado."
        )
    return empresa


def exigir_papel(
    *papeis: str,
) -> Callable[..., Coroutine[Any, Any, Membership]]:
    """Cria um guard que exige um dos papéis informados (senão 403)."""

    async def guard(
        membership: Annotated[Membership, Depends(get_current_membership)],
    ) -> Membership:
        if membership.papel not in papeis:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissão insuficiente.",
            )
        return membership

    return guard
