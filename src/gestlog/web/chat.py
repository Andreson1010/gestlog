"""Rota SSE do chat do copiloto (streaming da resposta ao operador)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.orm import Session

from gestlog.auth import get_current_empresa, get_current_user
from gestlog.config import Settings, get_settings
from gestlog.copilot import CopilotService
from gestlog.copilot.service import MENSAGEM_ERRO_COPILOTO
from gestlog.db.models import Empresa, User
from gestlog.llm import build_chat_model
from gestlog.web.ingestion_ui import get_sync_session

logger = logging.getLogger(__name__)

_MEDIA_TYPE_SSE = "text/event-stream"


@lru_cache(maxsize=1)
def get_chat_model() -> BaseChatModel:
    """Retorna (e memoiza) o modelo de chat usado pelo copiloto."""
    return build_chat_model(settings=get_settings())


def _evento(nome: str, texto: str) -> str:
    """Formata um evento SSE, quebrando o payload em linhas ``data:``."""
    linhas = texto.splitlines() or [""]
    corpo = "".join(f"data: {linha}\n" for linha in linhas)
    return f"event: {nome}\n{corpo}\n"


def _stream_resposta(resposta: str) -> Iterator[str]:
    """Emite a resposta do especialista e o evento de encerramento."""
    yield _evento("resposta", resposta)
    yield _evento("fim", "[DONE]")


def create_chat_router() -> APIRouter:
    """Cria a rota autenticada de chat com streaming SSE."""
    router = APIRouter()

    @router.get("/chat/stream")
    def chat_stream(
        pergunta: Annotated[str, Query(min_length=1)],
        empresa: Annotated[Empresa, Depends(get_current_empresa)],
        usuario: Annotated[User, Depends(get_current_user)],
        session: Annotated[Session, Depends(get_sync_session)],
        model: Annotated[BaseChatModel, Depends(get_chat_model)],
        settings: Annotated[Settings, Depends(get_settings)],
    ) -> StreamingResponse:
        """Responde a pergunta do operador em SSE, com os dados da empresa."""
        servico = CopilotService(
            session=session,
            empresa_id=empresa.id,
            user_id=usuario.id,
            model=model,
            settings=settings,
        )
        try:
            resposta = servico.answer(pergunta)
        except Exception:
            logger.exception("Falha ao responder a pergunta do copiloto")
            resposta = MENSAGEM_ERRO_COPILOTO
        return StreamingResponse(
            _stream_resposta(resposta),
            media_type=_MEDIA_TYPE_SSE,
            headers={"Cache-Control": "no-cache"},
        )

    return router
