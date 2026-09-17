"""Serviço de copiloto: roda o grafo com o contexto do tenant.

O serviço prende a sessão e a empresa em cada tool (via as fábricas de
``tools/``) e delega a resposta ao grafo multiagente. Nesta task o serviço também
estrutura a resposta como recomendação (texto, justificativa e fontes), detecta
dado insuficiente sem alucinar e persiste o turno e a ``Recommendation`` por
usuário e empresa. A F1 é read-only (AD-001): ainda não há redação de PII nem
medição de uso aqui — entram nas tasks seguintes.
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
from gestlog.repositories.conversations import (
    ConversationRepository,
    MessageRepository,
    RecommendationRepository,
)
from gestlog.tools.common import (
    FONTES_VAZIAS,
    ROTULO_FONTES,
    ROTULO_JUSTIFICATIVA,
    ROTULO_RESPOSTA,
)
from gestlog.tools.inventory import build_inventory_tools
from gestlog.tools.suppliers import build_supplier_tools
from gestlog.tools.transport import build_transport_tools

MENSAGEM_FORA_DE_ESCOPO = (
    "Não encontrei dados sobre essa solicitação na sua operação. "
    "Pergunte sobre estoque, fornecedores ou transporte."
)

MENSAGEM_INSUFICIENCIA = (
    "Não há dados suficientes na sua operação para recomendar com segurança. "
    "Importe ou complete os dados de estoque, fornecedores e transporte."
)

_SEPARADORES_FONTES = (";", ",")


@dataclass(frozen=True)
class Turno:
    """Par pergunta/resposta do histórico da conversa."""

    pergunta: str
    resposta: str


@dataclass(frozen=True)
class Recomendacao:
    """Recomendação estruturada, com justificativa e fontes do dado usado."""

    dominio: str
    texto: str
    justificativa: str = ""
    fontes: tuple[str, ...] = ()
    insuficiente: bool = False


def _separar_fontes(referencia: str) -> tuple[str, ...]:
    """Converte a string de fontes da tool comum em lista, sem o sentinela vazio."""
    texto = referencia.strip()
    if not texto or texto == FONTES_VAZIAS:
        return ()
    for separador in _SEPARADORES_FONTES:
        texto = texto.replace(separador, "|")
    return tuple(parte.strip() for parte in texto.split("|") if parte.strip())


def _quebrar_resposta(resposta: str) -> tuple[str, str, tuple[str, ...]]:
    """Separa texto, justificativa e fontes de uma resposta composta pela tool."""
    corpo = resposta
    prefixo = f"{ROTULO_RESPOSTA}:"
    if corpo.startswith(prefixo):
        corpo = corpo[len(prefixo) :].lstrip("\n")
    marcador_fontes = f"\n{ROTULO_FONTES}:"
    referencia = ""
    if marcador_fontes in corpo:
        corpo, referencia = corpo.rsplit(marcador_fontes, 1)
    marcador_justificativa = f"\n{ROTULO_JUSTIFICATIVA}:"
    justificativa = ""
    if marcador_justificativa in corpo:
        corpo, justificativa = corpo.rsplit(marcador_justificativa, 1)
    return corpo.strip(), justificativa.strip(), _separar_fontes(referencia)


def extrair_recomendacao(resposta: str, dominio: str) -> Recomendacao:
    """Estrutura a resposta em recomendação; sem base virá insuficiência."""
    if resposta == MENSAGEM_FORA_DE_ESCOPO:
        return Recomendacao(dominio=dominio, texto=resposta, insuficiente=True)
    texto, justificativa, fontes = _quebrar_resposta(resposta)
    if not texto or not fontes:
        return Recomendacao(
            dominio=dominio, texto=MENSAGEM_INSUFICIENCIA, insuficiente=True
        )
    return Recomendacao(
        dominio=dominio, texto=texto, justificativa=justificativa, fontes=fontes
    )


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
    recomendacao: Recomendacao | None = None,
) -> None:
    """Grava pergunta, resposta e (se houver base) a recomendação na conversa."""
    conversa = ConversationRepository(session).get_or_create(empresa_id, user_id)
    mensagens = MessageRepository(session)
    mensagens.add_message(conversa.id, "user", pergunta)
    mensagens.add_message(conversa.id, "assistant", resposta)
    if recomendacao is not None and not recomendacao.insuficiente:
        RecommendationRepository(session).add_recommendation(
            conversa.id,
            recomendacao.dominio,
            recomendacao.texto,
            recomendacao.justificativa,
            list(recomendacao.fontes),
        )
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
        """Roda o grafo, estrutura a recomendação, persiste o turno e responde."""
        resolvido = self.settings or get_settings()
        grafo = build_graph(
            model=self.model,
            settings=resolvido,
            specialist_tools=self.tools_por_dominio(),
        )
        estado = run_query(grafo, pergunta, recursion_limit=resolvido.recursion_limit)
        bruto = _texto_resposta(estado["messages"])
        dominio = str(estado.get("dominio", ""))
        recomendacao = extrair_recomendacao(bruto, dominio)
        resposta = recomendacao.texto if recomendacao.insuficiente else bruto
        registrar_turno(
            self.session,
            self.empresa_id,
            self.user_id,
            pergunta,
            resposta,
            recomendacao,
        )
        return resposta
