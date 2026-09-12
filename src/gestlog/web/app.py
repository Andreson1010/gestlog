"""Factory da aplicação web (FastAPI + Jinja2/HTMX)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from gestlog.auth import create_auth_router
from gestlog.config import Settings, get_settings
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

    @aplicacao.get("/", response_class=HTMLResponse)
    async def home(request: Request) -> HTMLResponse:
        return _TEMPLATES.TemplateResponse(request, "base.html", {"titulo": "gestlog"})

    return aplicacao
