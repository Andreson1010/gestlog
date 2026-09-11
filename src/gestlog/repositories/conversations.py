"""Repositórios de conversas, mensagens, recomendações e feedback."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from gestlog.db.models import Conversation, Feedback, Message, Recommendation
from gestlog.repositories.base import EmpresaScopedRepository


class ConversationRepository(EmpresaScopedRepository[Conversation]):
    """Conversas por empresa."""

    model = Conversation

    def create(self, empresa_id: UUID, user_id: UUID) -> Conversation:
        """Cria uma conversa para o usuário no empresa."""
        return self.add(Conversation(empresa_id=empresa_id, user_id=user_id))


class MessageRepository:
    """Mensagens de uma conversa.

    O isolamento por empresa é garantido ao obter a conversa via
    :class:`ConversationRepository` antes de listar/gravar mensagens.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_message(
        self, conversation_id: UUID, papel: str, conteudo_redigido: str
    ) -> Message:
        """Grava uma mensagem na conversa."""
        mensagem = Message(
            conversation_id=conversation_id,
            papel=papel,
            conteudo_redigido=conteudo_redigido,
        )
        self.session.add(mensagem)
        self.session.flush()
        return mensagem

    def list_by_conversation(self, conversation_id: UUID) -> list[Message]:
        """Lista as mensagens de uma conversa em ordem de criação."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        return list(self.session.execute(stmt).scalars().all())


class RecommendationRepository:
    """Recomendações de uma conversa."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_recommendation(
        self,
        conversation_id: UUID,
        dominio: str,
        texto: str,
        justificativa: str = "",
        fontes: list[str] | None = None,
    ) -> Recommendation:
        """Grava uma recomendação."""
        recomendacao = Recommendation(
            conversation_id=conversation_id,
            dominio=dominio,
            texto=texto,
            justificativa=justificativa,
            fontes=fontes,
        )
        self.session.add(recomendacao)
        self.session.flush()
        return recomendacao

    def list_by_conversation(self, conversation_id: UUID) -> list[Recommendation]:
        """Lista as recomendações de uma conversa."""
        stmt = select(Recommendation).where(
            Recommendation.conversation_id == conversation_id
        )
        return list(self.session.execute(stmt).scalars().all())


class FeedbackRepository:
    """Aceite/descarte de recomendações."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_feedback(
        self, recommendation_id: UUID, decisao: str, user_id: UUID
    ) -> Feedback:
        """Registra a decisão do operador sobre uma recomendação."""
        feedback = Feedback(
            recommendation_id=recommendation_id,
            decisao=decisao,
            user_id=user_id,
        )
        self.session.add(feedback)
        self.session.flush()
        return feedback
