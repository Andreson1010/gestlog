"""Rotas HTML de administração de usuários e papéis da empresa (T6)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, get_args
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from gestlog.auth import (
    accounts,
    exigir_papel,
    get_async_session,
    get_current_user,
)
from gestlog.db.models import Membership, User
from gestlog.web.schemas import Papel

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_PAPEIS = get_args(Papel)


async def _render(
    request: Request,
    session: AsyncSession,
    admin: Membership,
    email: str,
    erro: str | None = None,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    """Renderiza a página de administração com a lista atual de usuários."""
    vinculos = await accounts.listar_usuarios(session, admin.empresa_id)
    usuarios = [
        {"usuario_id": str(v.user_id), "email": u.email, "papel": v.papel}
        for v, u in vinculos
    ]
    return _TEMPLATES.TemplateResponse(
        request,
        "admin_usuarios.html",
        {
            "titulo": "Usuários · gestlog",
            "usuarios": usuarios,
            "papeis": _PAPEIS,
            "erro": erro,
            "email": email,
            "admin": True,
        },
        status_code=status_code,
    )


def create_admin_ui_router() -> APIRouter:
    """Cria a página HTML de gestão de usuários e os endpoints form-encoded."""
    router = APIRouter()

    @router.get("/admin/usuarios", response_class=HTMLResponse)
    async def pagina_usuarios(
        request: Request,
        admin: Annotated[Membership, Depends(exigir_papel("admin"))],
        usuario: Annotated[User, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_async_session)],
    ) -> Response:
        """Lista os usuários da empresa da sessão."""
        return await _render(request, session, admin, usuario.email)

    @router.post("/admin/usuarios/{usuario_id}/papel", response_class=HTMLResponse)
    async def alterar_papel(
        usuario_id: UUID,
        request: Request,
        admin: Annotated[Membership, Depends(exigir_papel("admin"))],
        usuario: Annotated[User, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_async_session)],
        papel: Annotated[str, Form()] = "",
    ) -> Response:
        """Altera o papel de um usuário da empresa e volta à lista."""
        if papel not in _PAPEIS:
            return await _render(
                request,
                session,
                admin,
                usuario.email,
                erro="Papel inválido.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        try:
            vinculo = await accounts.alterar_papel(
                session, admin.empresa_id, usuario_id, papel
            )
        except accounts.UltimoAdministradorError:
            return await _render(
                request,
                session,
                admin,
                usuario.email,
                erro="Não é possível rebaixar o último administrador.",
                status_code=status.HTTP_409_CONFLICT,
            )
        if vinculo is None:
            return await _render(
                request,
                session,
                admin,
                usuario.email,
                erro="Usuário não encontrado na empresa.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return RedirectResponse(
            url="/admin/usuarios", status_code=status.HTTP_303_SEE_OTHER
        )

    @router.post("/admin/usuarios/{usuario_id}/remover", response_class=HTMLResponse)
    async def remover_usuario(
        usuario_id: UUID,
        request: Request,
        admin: Annotated[Membership, Depends(exigir_papel("admin"))],
        usuario: Annotated[User, Depends(get_current_user)],
        session: Annotated[AsyncSession, Depends(get_async_session)],
    ) -> Response:
        """Remove o vínculo de um usuário da empresa e volta à lista."""
        try:
            removido = await accounts.remover_usuario(
                session, admin.empresa_id, usuario_id
            )
        except accounts.UltimoAdministradorError:
            return await _render(
                request,
                session,
                admin,
                usuario.email,
                erro="Não é possível remover o último administrador.",
                status_code=status.HTTP_409_CONFLICT,
            )
        if not removido:
            return await _render(
                request,
                session,
                admin,
                usuario.email,
                erro="Usuário não encontrado na empresa.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return RedirectResponse(
            url="/admin/usuarios", status_code=status.HTTP_303_SEE_OTHER
        )

    return router
