"""Rota de feedback (aceitar/descartar) das recomendações do copiloto (T22)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, status
from sqlalchemy.orm import Session

from gestlog.auth import get_current_empresa, get_current_user
from gestlog.db.models import Empresa, User
from gestlog.repositories.conversations import (
    FeedbackRepository,
    RecommendationRepository,
)
from gestlog.web.ingestion_ui import get_sync_session
from gestlog.web.schemas import DecisaoFeedback


def create_feedback_router() -> APIRouter:
    """Cria a rota que registra o aceite/descarte de uma recomendação."""
    router = APIRouter()

    @router.post(
        "/recomendacoes/{recommendation_id}/feedback",
        status_code=status.HTTP_201_CREATED,
    )
    def registrar_feedback(
        recommendation_id: UUID,
        decisao: Annotated[DecisaoFeedback, Form()],
        usuario: Annotated[User, Depends(get_current_user)],
        empresa: Annotated[Empresa, Depends(get_current_empresa)],
        session: Annotated[Session, Depends(get_sync_session)],
    ) -> dict[str, str]:
        """Persiste a decisão do operador sobre uma recomendação do seu tenant.

        Recebe o corpo em ``form`` para o HTMX da T23. Responde 404 quando a
        recomendação não pertence ao usuário na empresa da sessão, sem revelar
        se o id existe em outro tenant.
        """
        recomendacao = RecommendationRepository(session).get_do_usuario(
            recommendation_id, empresa.id, usuario.id
        )
        if recomendacao is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Não encontrado."
            )
        feedback = FeedbackRepository(session).add_feedback(
            recommendation_id, decisao, usuario.id
        )
        session.commit()
        return {"feedback_id": str(feedback.id), "decisao": feedback.decisao}

    return router
