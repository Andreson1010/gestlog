"""Rota de feedback (aceitar/descartar) das recomendações do copiloto (T22/T23)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from gestlog.auth import get_current_empresa, get_current_user
from gestlog.db.models import Empresa, User
from gestlog.repositories.conversations import (
    FeedbackRepository,
    RecommendationRepository,
)
from gestlog.web.ingestion_ui import get_sync_session
from gestlog.web.schemas import DecisaoFeedback

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def create_feedback_router() -> APIRouter:
    """Cria a rota que registra o aceite/descarte e devolve o fragmento."""
    router = APIRouter()

    @router.post("/recomendacoes/{recommendation_id}/feedback")
    def registrar_feedback(
        recommendation_id: UUID,
        decisao: Annotated[DecisaoFeedback, Form()],
        usuario: Annotated[User, Depends(get_current_user)],
        empresa: Annotated[Empresa, Depends(get_current_empresa)],
        session: Annotated[Session, Depends(get_sync_session)],
    ) -> HTMLResponse:
        """Persiste a decisão e devolve o fragmento HTMX atualizado.

        Responde 404 quando a recomendação não pertence ao usuário na empresa da
        sessão, sem revelar se o id existe em outro tenant. O corpo é ``form`` e
        a resposta é HTML para o swap do HTMX (T23).
        """
        recomendacao = RecommendationRepository(session).get_do_usuario(
            recommendation_id, empresa.id, usuario.id
        )
        if recomendacao is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Não encontrado."
            )
        FeedbackRepository(session).add_feedback(recommendation_id, decisao, usuario.id)
        session.commit()
        return _render_feedback(recommendation_id, decisao)

    return router


def _render_feedback(recommendation_id: UUID, decisao: str) -> HTMLResponse:
    """Renderiza o fragmento de aceitar/descartar de uma recomendação."""
    html = _TEMPLATES.env.get_template("_feedback.html").render(
        turno={"recomendacao_id": recommendation_id, "decisao": decisao}
    )
    return HTMLResponse(html)
