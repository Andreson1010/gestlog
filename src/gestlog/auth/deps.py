"""Dependências de usuário autenticado e resolução da empresa (tenancy).

O auth é a única camada com acesso assíncrono ao banco (AD-013), por isso a
resolução de vínculo/empresa é feita aqui, sobre ``AsyncSession``.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi_users.authentication import Authenticator
from sqlalchemy import case, select
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

COOKIE_EMPRESA_ATIVA = "gestlog_empresa_ativa"


async def get_current_user(
    user: Annotated[User, Depends(current_active_user)],
) -> User:
    """Devolve o usuário autenticado (401 se não houver sessão válida)."""
    return user


def _empresa_ativa_do_cookie(request: Request) -> UUID | None:
    """Lê o id de empresa ativa do cookie; valor malformado é ignorado."""
    crua = request.cookies.get(COOKIE_EMPRESA_ATIVA)
    if not crua:
        return None
    try:
        return UUID(crua)
    except ValueError:
        return None


async def _buscar_membership(
    session: AsyncSession, user_id: UUID, empresa_ativa: UUID | None = None
) -> Membership | None:
    """Busca o vínculo do usuário, preferindo a empresa ativa e depois a mais antiga.

    A preferência é apenas de ordenação: se a empresa ativa do cookie não
    corresponder a nenhum vínculo (ou o cookie estiver malformado), cai para
    o vínculo mais antigo — nunca nega acesso nem vaza outra empresa.
    """
    stmt = select(Membership).where(Membership.user_id == user_id)
    if empresa_ativa is not None:
        stmt = stmt.order_by(
            case((Membership.empresa_id == empresa_ativa, 0), else_=1),
            Membership.created_at,
            Membership.id,
        )
    else:
        stmt = stmt.order_by(Membership.created_at, Membership.id)
    return (await session.execute(stmt)).scalars().first()


async def get_current_membership(
    request: Request,
    user: Annotated[User, Depends(current_active_user)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Membership:
    """Resolve o vínculo do usuário com a empresa (403 se não houver).

    A empresa ativa vem do cookie (AD-015: seleção para múltiplos vínculos);
    sem cookie, ou com cookie que não casa com vínculo algum, usa o vínculo
    mais antigo de forma determinística.
    """
    membership = await _buscar_membership(
        session, user.id, _empresa_ativa_do_cookie(request)
    )
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
    request: Request,
    user: Annotated[User | None, Depends(current_active_user_optional)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Membership | None:
    """Devolve o vínculo do usuário, ou ``None`` sem usuário/empresa.

    Usado por páginas que decidem o que exibir conforme o papel, sem exigir
    um papel específico. Respeita a empresa ativa do cookie.
    """
    if user is None:
        return None
    return await _buscar_membership(session, user.id, _empresa_ativa_do_cookie(request))


async def get_current_empresa_optional(
    request: Request,
    user: Annotated[User | None, Depends(current_active_user_optional)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> Empresa | None:
    """Devolve a empresa da sessão, ou ``None`` sem usuário/vínculo.

    Usado por páginas que decidem o redirect de login por conta própria.
    Respeita a empresa ativa do cookie.
    """
    if user is None:
        return None
    membership = await _buscar_membership(
        session, user.id, _empresa_ativa_do_cookie(request)
    )
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
