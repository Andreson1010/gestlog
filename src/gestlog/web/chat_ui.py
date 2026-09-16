"""Rotas web da tela de chat do copiloto (T19)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from gestlog.auth import current_active_user_optional
from gestlog.db.models import User

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def create_chat_ui_router() -> APIRouter:
    """Cria as rotas da página de chat e do turno consumido por HTMX/SSE."""
    router = APIRouter()

    @router.get("/chat", response_class=HTMLResponse)
    def pagina_chat(
        request: Request,
        usuario: Annotated[User | None, Depends(current_active_user_optional)],
    ) -> Response:
        """Exibe a tela de chat; sem sessão redireciona ao login."""
        if usuario is None:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        return _TEMPLATES.TemplateResponse(
            request, "chat.html", {"titulo": "Chat · gestlog"}
        )

    @router.get("/chat/pergunta", response_class=HTMLResponse)
    def turno_chat(
        request: Request,
        pergunta: Annotated[str, Query(min_length=1)],
        usuario: Annotated[User | None, Depends(current_active_user_optional)],
    ) -> Response:
        """Anexa o turno do operador e abre a assinatura SSE da resposta."""
        if usuario is None:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        return _TEMPLATES.TemplateResponse(
            request, "chat_turno.html", {"pergunta": pergunta}
        )

    return router
