"""Factory da aplicação web (FastAPI + Jinja2/HTMX)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi_users import exceptions
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from gestlog.auth import (
    create_auth_router,
    current_active_user_optional,
    get_async_session,
    get_current_membership_optional,
)
from gestlog.auth.accounts import criar_conta
from gestlog.config import Settings, get_settings
from gestlog.db.models import Membership, User
from gestlog.web.admin import create_admin_router
from gestlog.web.admin_ui import create_admin_ui_router
from gestlog.web.chat import create_chat_router
from gestlog.web.chat_ui import create_chat_ui_router
from gestlog.web.feedback import create_feedback_router
from gestlog.web.ingestion_ui import create_ingestion_router
from gestlog.web.kpis import create_kpis_router
from gestlog.web.onboarding import create_onboarding_router
from gestlog.web.schemas import ContaCreate

_BASE_DIR = Path(__file__).parent
_TEMPLATES = Jinja2Templates(directory=str(_BASE_DIR / "templates"))


def _render_cadastro(
    request: Request,
    erro: str | None = None,
    nome_empresa: str = "",
    email: str = "",
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    """Renderiza o formulário de cadastro, opcionalmente com erro."""
    return _TEMPLATES.TemplateResponse(
        request,
        "cadastro.html",
        {
            "titulo": "Criar conta · gestlog",
            "erro": erro,
            "nome_empresa": nome_empresa,
            "email": email,
        },
        status_code=status_code,
    )


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
    aplicacao.include_router(create_admin_router())
    aplicacao.include_router(create_admin_ui_router())
    aplicacao.include_router(create_ingestion_router())
    aplicacao.include_router(create_chat_ui_router())
    aplicacao.include_router(create_kpis_router())
    aplicacao.include_router(create_chat_router())
    aplicacao.include_router(create_feedback_router())

    @aplicacao.get("/", response_class=HTMLResponse)
    async def home(
        request: Request,
        usuario: Annotated[User | None, Depends(current_active_user_optional)],
        membership: Annotated[
            Membership | None, Depends(get_current_membership_optional)
        ],
    ) -> Response:
        """Página inicial autenticada; sem sessão redireciona ao login."""
        if usuario is None:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        return _TEMPLATES.TemplateResponse(
            request,
            "home.html",
            {
                "titulo": "gestlog",
                "email": usuario.email,
                "admin": membership is not None and membership.papel == "admin",
            },
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

    @aplicacao.get("/cadastro", response_class=HTMLResponse)
    async def cadastro_form(
        request: Request,
        usuario: Annotated[User | None, Depends(current_active_user_optional)],
    ) -> Response:
        """Formulário público de criação de conta; com sessão vai à home."""
        if usuario is not None:
            return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        return _render_cadastro(request)

    @aplicacao.post("/cadastro", response_class=HTMLResponse)
    async def cadastro(
        request: Request,
        session: Annotated[AsyncSession, Depends(get_async_session)],
        nome_empresa: Annotated[str, Form()] = "",
        email: Annotated[str, Form()] = "",
        senha: Annotated[str, Form()] = "",
    ) -> Response:
        """Cria a empresa e o usuário admin; em erro reexibe o formulário."""
        try:
            conta = ContaCreate(nome_empresa=nome_empresa, email=email, senha=senha)
        except ValidationError:
            return _render_cadastro(
                request,
                "Confira os dados informados.",
                nome_empresa,
                email,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        try:
            await criar_conta(session, conta.nome_empresa, conta.email, conta.senha)
        except exceptions.UserAlreadyExists:
            return _render_cadastro(
                request,
                "E-mail já cadastrado.",
                nome_empresa,
                email,
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except IntegrityError:
            await session.rollback()
            return _render_cadastro(
                request,
                "E-mail já cadastrado.",
                nome_empresa,
                email,
                status_code=status.HTTP_409_CONFLICT,
            )
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    return aplicacao
