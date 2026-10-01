"""Dashboard de KPIs por empresa e período (KPI-01)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from gestlog.auth import current_active_user_optional, exigir_papel
from gestlog.correcoes import PAPEIS_APROVADORES
from gestlog.db.models import Membership, User
from gestlog.repositories.kpis import KpiRepository
from gestlog.web.ingestion_ui import get_sync_session
from gestlog.web.periodo import fim_do_dia, inicio_do_dia

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def create_kpis_router() -> APIRouter:
    """Cria a rota do dashboard de indicadores da empresa."""
    router = APIRouter()

    @router.get("/kpis")
    def pagina_kpis(
        request: Request,
        usuario: Annotated[User | None, Depends(current_active_user_optional)],
        vinculo: Annotated[Membership, Depends(exigir_papel("admin", "gestor"))],
        session: Annotated[Session, Depends(get_sync_session)],
        desde: date | None = None,
        ate: date | None = None,
    ) -> Response:
        """Exibe os KPIs da empresa no período informado (ou de todo o histórico)."""
        resumo = KpiRepository(session).resumo(
            vinculo.empresa_id, inicio_do_dia(desde), fim_do_dia(ate)
        )
        return _TEMPLATES.TemplateResponse(
            request,
            "kpis.html",
            {
                "titulo": "Indicadores · gestlog",
                "kpis": resumo,
                "desde": desde.isoformat() if desde else "",
                "ate": ate.isoformat() if ate else "",
                "email": usuario.email if usuario else "",
                "admin": vinculo.papel == "admin",
                "pode_aprovar": vinculo.papel in PAPEIS_APROVADORES,
            },
        )

    return router
