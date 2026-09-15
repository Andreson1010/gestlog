"""Serviço de copiloto: roda o grafo com o contexto do tenant.

O serviço prende a sessão e a empresa em cada tool (via as fábricas de
``tools/``) e delega a resposta ao grafo multiagente. A F1 é read-only (AD-001):
não há redação de PII, medição ou persistência aqui — entram nas tasks seguintes.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import BaseTool
from sqlalchemy.orm import Session

from gestlog.config import Settings
from gestlog.graph import build_graph, run_query
from gestlog.repositories.catalog import (
    StockRepository,
    SupplierRepository,
    TransportRepository,
)
from gestlog.tools.inventory import build_inventory_tools
from gestlog.tools.suppliers import build_supplier_tools
from gestlog.tools.transport import build_transport_tools

MENSAGEM_FORA_DE_ESCOPO = (
    "Não encontrei dados sobre essa solicitação na sua operação. "
    "Pergunte sobre estoque, fornecedores ou transporte."
)
_LIMITE_RECURSAO_PADRAO = 25


def _texto_resposta(messages: Sequence[BaseMessage]) -> str:
    """Devolve a última resposta do especialista ou o aviso de fora de escopo."""
    for mensagem in reversed(messages):
        if isinstance(mensagem, AIMessage) and mensagem.content:
            return str(mensagem.content)
    return MENSAGEM_FORA_DE_ESCOPO


@dataclass(frozen=True)
class CopilotService:
    """Responde perguntas logísticas com os dados do tenant (read-only)."""

    session: Session
    empresa_id: UUID
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

    def answer(self, pergunta: str) -> str:
        """Roda o grafo com o contexto do tenant e devolve a resposta final."""
        grafo = build_graph(
            model=self.model,
            settings=self.settings,
            specialist_tools=self.tools_por_dominio(),
        )
        limite = (
            self.settings.recursion_limit
            if self.settings is not None
            else _LIMITE_RECURSAO_PADRAO
        )
        estado = run_query(grafo, pergunta, recursion_limit=limite)
        return _texto_resposta(estado["messages"])
