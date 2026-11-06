"""Rota SSE do chat do copiloto (streaming da resposta ao operador)."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from langchain_core.language_models.chat_models import BaseChatModel
from sqlalchemy.orm import Session

from gestlog.auth import get_current_empresa, get_current_user
from gestlog.config import Settings, get_settings
from gestlog.copilot import MENSAGEM_ERRO_COPILOTO, CopilotService
from gestlog.db.models import Empresa, User
from gestlog.llm import build_chat_model
from gestlog.web.feedback import fragmento_feedback
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


def _stream_resposta(resposta: str, fragmento: str) -> Iterator[str]:
    """Emite a resposta, o fragmento de feedback do turno e o encerramento.

    O fragmento vai no evento ``fontes`` (AD-019): traz os botões
    aceitar/descartar da recomendação recém-criada para o turno ao vivo,
    sem exigir recarregar o histórico. Sem recomendação, o evento não é
    emitido e o turno fica sem botões.
    """
    yield _evento("resposta", resposta)
    if fragmento:
        yield _evento("fontes", fragmento)
    yield _evento("fim", "[DONE]")


def _fragmento_da_recomendacao(recomendacao_id: UUID | None) -> str:
    """HTML de aceitar/descartar da recomendação do turno recém-criado.

    O id vem de ``answer_com_recomendacao`` (turno deste stream): nesse caminho
    não há decisão anterior (quota estourada e fora de escopo devolvem ``None``).
    """
    if recomendacao_id is None:
        return ""
    try:
        return fragmento_feedback(recomendacao_id, None)
    except Exception:
        logger.exception("Falha ao montar o fragmento de feedback do turno")
        return ""


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
            resposta, recomendacao_id = servico.answer_com_recomendacao(pergunta)
        except Exception:
            logger.exception("Falha ao responder a pergunta do copiloto")
            resposta = MENSAGEM_ERRO_COPILOTO
            fragmento = ""
        else:
            fragmento = _fragmento_da_recomendacao(recomendacao_id)
        return StreamingResponse(
            _stream_resposta(resposta, fragmento),
            media_type=_MEDIA_TYPE_SSE,
            headers={"Cache-Control": "no-cache"},
        )

    return router
