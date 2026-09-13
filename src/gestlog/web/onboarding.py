"""Rotas de onboarding da conta e convite de usuários."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_users import exceptions
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from gestlog.auth import accounts, exigir_papel
from gestlog.auth.db import get_async_session
from gestlog.db.models import Membership
from gestlog.web.schemas import ContaCreate, ConviteCreate


def create_onboarding_router() -> APIRouter:
    """Cria as rotas de criação de conta e convite por e-mail."""
    router = APIRouter()

    @router.post("/onboarding", status_code=status.HTTP_201_CREATED)
    async def onboarding(
        corpo: ContaCreate,
        session: Annotated[AsyncSession, Depends(get_async_session)],
    ) -> dict[str, str]:
        try:
            empresa, usuario = await accounts.criar_conta(
                session, corpo.nome_empresa, corpo.email, corpo.senha
            )
        except exceptions.UserAlreadyExists as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="E-mail já cadastrado.",
            ) from exc
        return {"empresa_id": str(empresa.id), "usuario_id": str(usuario.id)}

    @router.post("/empresa/convites", status_code=status.HTTP_201_CREATED)
    async def convidar(
        corpo: ConviteCreate,
        admin: Annotated[Membership, Depends(exigir_papel("admin"))],
        session: Annotated[AsyncSession, Depends(get_async_session)],
    ) -> dict[str, str]:
        try:
            vinculo = await accounts.convidar_usuario(
                session,
                admin.empresa_id,
                corpo.email,
                corpo.papel,
                corpo.senha,
            )
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Usuário já vinculado à empresa.",
            ) from exc
        return {"usuario_id": str(vinculo.user_id), "papel": vinculo.papel}

    return router
