"""Rotas web de upload e histórico de importação."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from gestlog.auth import (
    current_active_user_optional,
    get_current_empresa,
    get_current_membership_optional,
)
from gestlog.config import get_settings
from gestlog.correcoes import PAPEIS_APROVADORES
from gestlog.db.models import Empresa, Membership, User
from gestlog.db.session import build_engine, build_session_factory
from gestlog.ingestion import ErroImportacao, historico, importar

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_TIPOS = ("estoque", "fornecedores", "transporte")


@lru_cache(maxsize=1)
def _get_sync_engine() -> Engine:
    """Retorna (e memoiza) o engine síncrono usado pelo fluxo de importação."""
    return build_engine(get_settings())


@lru_cache(maxsize=1)
def _get_sync_factory() -> sessionmaker[Session]:
    """Retorna (e memoiza) a fábrica de sessões síncronas de importação."""
    return build_session_factory(_get_sync_engine())


def get_sync_session() -> Iterator[Session]:
    """Fornece uma sessão síncrona por requisição para a importação."""
    with _get_sync_factory()() as session:
        yield session


def create_ingestion_router() -> APIRouter:
    """Cria as rotas de upload, resultado e histórico de importação."""
    router = APIRouter()

    @router.get("/importar", response_class=HTMLResponse)
    def pagina_importar(
        request: Request,
        usuario: Annotated[User | None, Depends(current_active_user_optional)],
        membership: Annotated[
            Membership | None, Depends(get_current_membership_optional)
        ],
    ) -> Response:
        """Exibe o formulário de upload; sem sessão redireciona ao login."""
        if usuario is None:
            return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        return _TEMPLATES.TemplateResponse(
            request,
            "importar.html",
            {
                "titulo": "Importar · gestlog",
                "tipos": _TIPOS,
                "email": usuario.email,
                "admin": membership is not None and membership.papel == "admin",
                "pode_aprovar": membership is not None
                and membership.papel in PAPEIS_APROVADORES,
            },
        )

    @router.post("/importar", response_class=HTMLResponse)
    def enviar_arquivo(
        request: Request,
        empresa: Annotated[Empresa, Depends(get_current_empresa)],
        session: Annotated[Session, Depends(get_sync_session)],
        tipo: Annotated[str, Form()],
        arquivo: Annotated[UploadFile, File()],
    ) -> Response:
        """Processa o arquivo e devolve o resultado (parcial HTMX)."""
        try:
            conteudo = arquivo.file.read()
            job = importar(session, empresa.id, tipo, conteudo, arquivo.filename or "")
            session.commit()
        except ErroImportacao as exc:
            session.rollback()
            return _TEMPLATES.TemplateResponse(
                request,
                "importar_resultado.html",
                {"titulo": "", "erro": str(exc), "job": None},
            )
        return _TEMPLATES.TemplateResponse(
            request,
            "importar_resultado.html",
            {"titulo": "", "erro": None, "job": job},
        )

    @router.get("/importar/historico", response_class=HTMLResponse)
    def pagina_historico(
        request: Request,
        usuario: Annotated[User | None, Depends(current_active_user_optional)],
        membership: Annotated[
            Membership | None, Depends(get_current_membership_optional)
        ],
        empresa: Annotated[Empresa, Depends(get_current_empresa)],
        session: Annotated[Session, Depends(get_sync_session)],
    ) -> Response:
        """Exibe as importações da empresa, mais recentes primeiro."""
        return _TEMPLATES.TemplateResponse(
            request,
            "historico.html",
            {
                "titulo": "Histórico · gestlog",
                "jobs": historico(session, empresa.id),
                "email": usuario.email if usuario else "",
                "admin": membership is not None and membership.papel == "admin",
                "pode_aprovar": membership is not None
                and membership.papel in PAPEIS_APROVADORES,
            },
        )

    return router
