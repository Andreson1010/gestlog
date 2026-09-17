"""Serviço de copiloto: roda o grafo com o contexto do tenant.

O serviço prende a sessão e a empresa em cada tool (via as fábricas de
``tools/``) e delega a resposta ao grafo multiagente. Nesta task o serviço também
persiste o turno (pergunta/resposta) por usuário e empresa, para que o histórico
seja recuperado ao voltar. A F1 é read-only (AD-001): ainda não há redação de PII
nem medição de uso aqui — entram nas tasks seguintes.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import BaseTool
from sqlalchemy.orm import Session

from gestlog.config import Settings, get_settings
from gestlog.db.models import Message
from gestlog.graph import build_graph, run_query
from gestlog.repositories.catalog import (
    StockRepository,
    SupplierRepository,
    TransportRepository,
)
from gestlog.repositories.conversations import ConversationRepository, MessageRepository
from gestlog.tools.inventory import build_inventory_tools
from gestlog.tools.suppliers import build_supplier_tools
from gestlog.tools.transport import build_transport_tools

MENSAGEM_FORA_DE_ESCOPO = (
    "Não encontrei dados sobre essa solicitação na sua operação. "
    "Pergunte sobre estoque, fornecedores ou transporte."
)


@dataclass(frozen=True)
class Turno:
    """Par pergunta/resposta do histórico da conversa."""

    pergunta: str
    resposta: str


def _texto_resposta(messages: Sequence[BaseMessage]) -> str:
    """Devolve a última resposta do especialista ou o aviso de fora de escopo."""
    for mensagem in reversed(messages):
        if isinstance(mensagem, AIMessage) and mensagem.content:
            return str(mensagem.content)
    return MENSAGEM_FORA_DE_ESCOPO


def _montar_turnos(mensagens: Sequence[Message]) -> list[Turno]:
    """Agrupa mensagens em turnos de pergunta/resposta, na ordem de criação."""
    turnos: list[Turno] = []
    pergunta: str | None = None
    for mensagem in mensagens:
        if mensagem.papel == "user":
            pergunta = mensagem.conteudo_redigido
        elif mensagem.papel == "assistant":
            turnos.append(Turno(pergunta or "", mensagem.conteudo_redigido))
            pergunta = None
    if pergunta is not None:
        turnos.append(Turno(pergunta, ""))
    return turnos


def carregar_historico(
    session: Session, empresa_id: UUID, user_id: UUID
) -> list[Turno]:
    """Carrega os turnos da conversa do usuário, restritos à empresa."""
    conversa = ConversationRepository(session).get_by_user(empresa_id, user_id)
    if conversa is None:
        return []
    mensagens = MessageRepository(session).list_by_conversation(conversa.id)
    return _montar_turnos(mensagens)


def registrar_turno(
    session: Session,
    empresa_id: UUID,
    user_id: UUID,
    pergunta: str,
    resposta: str,
) -> None:
    """Grava pergunta e resposta na conversa do usuário e confirma a transação."""
    conversa = ConversationRepository(session).get_or_create(empresa_id, user_id)
    mensagens = MessageRepository(session)
    mensagens.add_message(conversa.id, "user", pergunta)
    mensagens.add_message(conversa.id, "assistant", resposta)
    session.commit()


@dataclass(frozen=True)
class CopilotService:
    """Responde perguntas logísticas com os dados do tenant (read-only)."""

    session: Session
    empresa_id: UUID
    user_id: UUID
    model: BaseChatModel
    settings: Settings | None = None

    def tools_por_dominio(self) -> dict[str, Sequence[BaseTool]]:
        """Constrói as tools de cada domínio amarradas ao tenant da sessão."""
        return {
            "estoque": build_inventory_tools(
                StockRepository(self.session), self.empresa_id
            ),
            "fornecedores": build_supplier_tools(
                SupplierRepository(self.session), self.empresa_id
            ),
            "transporte": build_transport_tools(
                TransportRepository(self.session), self.empresa_id
            ),
        }

    def historico(self) -> list[Turno]:
        """Devolve os turnos já gravados da conversa do usuário no tenant."""
        return carregar_historico(self.session, self.empresa_id, self.user_id)

    def answer(self, pergunta: str) -> str:
        """Roda o grafo, persiste o turno e devolve a resposta final."""
        resolvido = self.settings or get_settings()
        grafo = build_graph(
            model=self.model,
            settings=resolvido,
            specialist_tools=self.tools_por_dominio(),
        )
        estado = run_query(grafo, pergunta, recursion_limit=resolvido.recursion_limit)
        resposta = _texto_resposta(estado["messages"])
        registrar_turno(self.session, self.empresa_id, self.user_id, pergunta, resposta)
        return resposta
