"""Rotas web da tela de chat do copiloto (T19) e do seu histórico (T20)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from gestlog.auth import current_active_user_optional, get_current_empresa_optional
from gestlog.copilot import carregar_historico
from gestlog.db.models import Empresa, User
from gestlog.web.ingestion_ui import get_sync_session

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def create_chat_ui_router() -> APIRouter:
    """Cria as rotas da página de chat e do turno consumido por HTMX/SSE."""
    router = APIRouter()

    @router.get("/chat", response_class=HTMLResponse)
    def pagina_chat(
        request: Request,
        usuario: Annotated[User | None, Depends(current_active_user_optional)],
        empresa: Annotated[Empresa | None, Depends(get_current_empresa_optional)],
        session: Annotated[Session, Depends(get_sync_session)],
    ) -> Response:
        """Exibe a tela de chat com o histórico; sem sessão vai ao login."""
        if usuario is None:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        turnos = (
            carregar_historico(session, empresa.id, usuario.id)
            if empresa is not None
            else []
        )
        return _TEMPLATES.TemplateResponse(
            request, "chat.html", {"titulo": "Chat · gestlog", "turnos": turnos}
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
