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

    def get_by_user(self, empresa_id: UUID, user_id: UUID) -> Conversation | None:
        """Busca a conversa do usuário no empresa, restrita ao tenant."""
        stmt = (
            select(Conversation)
            .where(
                Conversation.empresa_id == empresa_id,
                Conversation.user_id == user_id,
            )
            .order_by(Conversation.created_at, Conversation.id)
        )
        return self.session.execute(stmt).scalars().first()

    def get_or_create(self, empresa_id: UUID, user_id: UUID) -> Conversation:
        """Devolve a conversa do usuário no empresa, criando-a se não existir."""
        conversa = self.get_by_user(empresa_id, user_id)
        if conversa is None:
            conversa = self.create(empresa_id, user_id)
        return conversa


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
            .order_by(Message.created_at, Message.id)
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

    def get_do_usuario(
        self, recommendation_id: UUID, empresa_id: UUID, user_id: UUID
    ) -> Recommendation | None:
        """Busca a recomendação do usuário no empresa, via conversa.

        É a guarda de tenancy e de autoria: só devolve a recomendação se a
        conversa pertencer ao mesmo ``empresa_id`` **e** ``user_id`` da sessão.
        Devolve ``None`` para id inexistente e para recurso de outro tenant/
        usuário, de modo que a rota responda 404 sem revelar existência.
        """
        stmt = (
            select(Recommendation)
            .join(Conversation, Recommendation.conversation_id == Conversation.id)
            .where(
                Recommendation.id == recommendation_id,
                Conversation.empresa_id == empresa_id,
                Conversation.user_id == user_id,
            )
        )
        return self.session.execute(stmt).scalar_one_or_none()


class FeedbackRepository:
    """Aceite/descarte de recomendações.

    O isolamento por empresa não é aplicado aqui: quem grava/lê deve antes
    autorizar a recomendação via :meth:`RecommendationRepository.get_do_usuario`,
    exatamente como :class:`MessageRepository` faz com a conversa. O histórico é
    *append-only* (sem upsert): uma mesma recomendação pode acumular decisões, e
    consumidores de KPI devem usar a última por recomendação.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_feedback(
        self, recommendation_id: UUID, decisao: str, user_id: UUID
    ) -> Feedback:
        """Registra mais uma decisão do operador (somente inserção)."""
        feedback = Feedback(
            recommendation_id=recommendation_id,
            decisao=decisao,
            user_id=user_id,
        )
        self.session.add(feedback)
        self.session.flush()
        return feedback

    def list_by_recommendation(self, recommendation_id: UUID) -> list[Feedback]:
        """Lista as decisões da recomendação, da mais antiga à mais recente.

        A última posição é a decisão vigente; use-a para KPI, não a contagem
        total, que somaria trocas de decisão.
        """
        stmt = (
            select(Feedback)
            .where(Feedback.recommendation_id == recommendation_id)
            .order_by(Feedback.created_at, Feedback.id)
        )
        return list(self.session.execute(stmt).scalars().all())
