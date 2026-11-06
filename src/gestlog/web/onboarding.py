"""Rotas de onboarding da conta e convite de usuários."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_users import exceptions
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from gestlog.auth import accounts, exigir_papel
from gestlog.auth.accounts import (
    ConviteDuplicadoError,
    ConviteEmailRegistradoError,
    ConviteInvalidoError,
)
from gestlog.auth.db import get_async_session
from gestlog.config import Settings, get_settings
from gestlog.db.models import Membership
from gestlog.web.rate_limit import limitar
from gestlog.web.schemas import (
    ContaCreate,
    ConviteAceiteCreate,
    ConviteCreate,
)


def create_onboarding_router() -> APIRouter:
    """Cria as rotas de criação de conta e convite por token (AD-015)."""
    router = APIRouter(dependencies=[Depends(limitar("onboarding"))])

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
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> dict[str, str]:
        """Cria o convite e devolve o token (entrega por e-mail é futura)."""
        try:
            _, token = await accounts.criar_convite(
                session,
                admin.empresa_id,
                corpo.email,
                corpo.papel,
                settings.convite_validade_dias,
            )
        except ConviteDuplicadoError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="E-mail já registrado no sistema; convite só cria conta nova.",
            ) from exc
        return {"email": corpo.email, "papel": corpo.papel, "token": token}

    @router.post("/convites/aceitar", status_code=status.HTTP_201_CREATED)
    async def aceitar_convite(
        corpo: ConviteAceiteCreate,
        session: Annotated[AsyncSession, Depends(get_async_session)],
    ) -> dict[str, str]:
        """Troca o token válido por conta nova na empresa, senha escolhida."""
        try:
            usuario, convite = await accounts.aceitar_convite(
                session, corpo.token, corpo.senha
            )
        except ConviteInvalidoError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Convite inválido, expirado ou já utilizado.",
            ) from exc
        except ConviteEmailRegistradoError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="E-mail já registrado; vincule-se autenticado (fluxo futuro).",
            ) from exc
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Convite já utilizado ou conta em criação; tente novamente.",
            ) from exc
        return {
            "usuario_id": str(usuario.id),
            "email": usuario.email,
            "empresa_id": str(convite.empresa_id),
            "papel": convite.papel,
        }

    return router
