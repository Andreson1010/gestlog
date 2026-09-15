"""Factory da aplicação web (FastAPI + Jinja2/HTMX)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from gestlog.auth import create_auth_router, current_active_user_optional
from gestlog.config import Settings, get_settings
from gestlog.db.models import User
from gestlog.web.chat import create_chat_router
from gestlog.web.ingestion_ui import create_ingestion_router
from gestlog.web.onboarding import create_onboarding_router

_BASE_DIR = Path(__file__).parent
_TEMPLATES = Jinja2Templates(directory=str(_BASE_DIR / "templates"))


def create_app(settings: Settings | None = None) -> FastAPI:
    """Monta a aplicação: estáticos, templates e routers."""
    resolved = settings or get_settings()
    aplicacao = FastAPI(title="gestlog")
    aplicacao.mount(
        "/static",
        StaticFiles(directory=str(_BASE_DIR / "static")),
        name="static",
    )
    aplicacao.include_router(create_auth_router(resolved), prefix="/auth")
    aplicacao.include_router(create_onboarding_router())
    aplicacao.include_router(create_ingestion_router())
    aplicacao.include_router(create_chat_router())

    @aplicacao.get("/", response_class=HTMLResponse)
    async def home(
        request: Request,
        usuario: Annotated[User | None, Depends(current_active_user_optional)],
    ) -> Response:
        """Página inicial autenticada; sem sessão redireciona ao login."""
        if usuario is None:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        return _TEMPLATES.TemplateResponse(
            request, "home.html", {"titulo": "gestlog", "email": usuario.email}
        )

    @aplicacao.get("/login", response_class=HTMLResponse)
    async def login(
        request: Request,
        usuario: Annotated[User | None, Depends(current_active_user_optional)],
    ) -> Response:
        """Formulário de login; com sessão ativa redireciona à home."""
        if usuario is not None:
            return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        return _TEMPLATES.TemplateResponse(
            request, "login.html", {"titulo": "Entrar · gestlog"}
        )

    return aplicacao
