"""Dashboard de KPIs por empresa e período (KPI-01)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from gestlog.auth import exigir_papel
from gestlog.db.models import Membership
from gestlog.repositories.kpis import KpiRepository
from gestlog.web.ingestion_ui import get_sync_session

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _inicio(valor: date | None) -> datetime | None:
    """Converte a data inicial no primeiro instante do dia (UTC)."""
    return datetime.combine(valor, time.min, tzinfo=UTC) if valor else None


def _fim(valor: date | None) -> datetime | None:
    """Converte a data final no último instante do dia (UTC)."""
    return datetime.combine(valor, time.max, tzinfo=UTC) if valor else None


def create_kpis_router() -> APIRouter:
    """Cria a rota do dashboard de indicadores da empresa."""
    router = APIRouter()

    @router.get("/kpis")
    def pagina_kpis(
        request: Request,
        vinculo: Annotated[Membership, Depends(exigir_papel("admin", "gestor"))],
        session: Annotated[Session, Depends(get_sync_session)],
        desde: date | None = None,
        ate: date | None = None,
    ) -> Response:
        """Exibe os KPIs da empresa no período informado (ou de todo o histórico)."""
        resumo = KpiRepository(session).resumo(
            vinculo.empresa_id, _inicio(desde), _fim(ate)
        )
        return _TEMPLATES.TemplateResponse(
            request,
            "kpis.html",
            {
                "titulo": "Indicadores · gestlog",
                "kpis": resumo,
                "desde": desde.isoformat() if desde else "",
                "ate": ate.isoformat() if ate else "",
            },
        )

    return router
