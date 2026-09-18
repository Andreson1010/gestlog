"""Rotas de gestão de usuários e papéis da empresa (admin)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from gestlog.auth import accounts, exigir_papel
from gestlog.auth.db import get_async_session
from gestlog.db.models import Membership
from gestlog.web.schemas import PapelAtualizar


def create_admin_router() -> APIRouter:
    """Cria as rotas de listagem, mudança de papel e remoção de usuários."""
    router = APIRouter()

    @router.get("/empresa/usuarios")
    async def listar_usuarios(
        admin: Annotated[Membership, Depends(exigir_papel("admin"))],
        session: Annotated[AsyncSession, Depends(get_async_session)],
    ) -> list[dict[str, str]]:
        """Lista os usuários da empresa da sessão."""
        vinculos = await accounts.listar_usuarios(session, admin.empresa_id)
        return [
            {"usuario_id": str(v.user_id), "email": u.email, "papel": v.papel}
            for v, u in vinculos
        ]

    @router.patch("/empresa/usuarios/{usuario_id}")
    async def alterar_papel(
        usuario_id: UUID,
        corpo: PapelAtualizar,
        admin: Annotated[Membership, Depends(exigir_papel("admin"))],
        session: Annotated[AsyncSession, Depends(get_async_session)],
    ) -> dict[str, str]:
        """Altera o papel de um usuário da empresa."""
        try:
            vinculo = await accounts.alterar_papel(
                session, admin.empresa_id, usuario_id, corpo.papel
            )
        except accounts.UltimoAdministradorError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Não é possível rebaixar o último administrador.",
            ) from exc
        if vinculo is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado na empresa.",
            )
        return {"usuario_id": str(vinculo.user_id), "papel": vinculo.papel}

    @router.delete(
        "/empresa/usuarios/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT
    )
    async def remover_usuario(
        usuario_id: UUID,
        admin: Annotated[Membership, Depends(exigir_papel("admin"))],
        session: Annotated[AsyncSession, Depends(get_async_session)],
    ) -> Response:
        """Remove o vínculo de um usuário com a empresa (revoga o acesso)."""
        try:
            removido = await accounts.remover_usuario(
                session, admin.empresa_id, usuario_id
            )
        except accounts.UltimoAdministradorError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Não é possível remover o último administrador.",
            ) from exc
        if not removido:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado na empresa.",
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
