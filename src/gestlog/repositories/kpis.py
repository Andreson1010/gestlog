"""Agregações de KPIs por empresa e período (KPI-01)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from gestlog.db.models import (
    Conversation,
    Feedback,
    Message,
    Recommendation,
    StockItem,
    Supplier,
    TransportRecord,
)


@dataclass(frozen=True)
class ResumoKpis:
    """Números agregados de adoção, aceitação e cobertura de dados."""

    conversas: int = 0
    perguntas: int = 0
    recomendacoes: int = 0
    aceitas: int = 0
    descartadas: int = 0
    itens_estoque: int = 0
    fornecedores: int = 0
    registros_transporte: int = 0

    @property
    def decisoes(self) -> int:
        """Decisões vigentes contabilizadas (aceitas + descartadas)."""
        return self.aceitas + self.descartadas

    @property
    def taxa_aceitacao(self) -> float:
        """Fração de recomendações aceitas sobre as decididas (0.0 sem decisões)."""
        return self.aceitas / self.decisoes if self.decisoes else 0.0

    @property
    def cobertura_dados(self) -> int:
        """Total atual de registros de estoque, fornecedores e transporte.

        É um retrato (snapshot) do estado presente, sem recorte de período: as
        tabelas de catálogo representam a última versão importada, não um
        histórico de versões.
        """
        return self.itens_estoque + self.fornecedores + self.registros_transporte


def _periodo(
    condicoes: list,
    coluna: object,
    desde: datetime | None,
    ate: datetime | None,
) -> list:
    """Acrescenta os limites de período (inclusivos) às condições."""
    if desde is not None:
        condicoes.append(coluna >= desde)  # type: ignore[operator]
    if ate is not None:
        condicoes.append(coluna <= ate)  # type: ignore[operator]
    return condicoes


class KpiRepository:
    """Leitura dos KPIs de uma empresa, com recorte de período opcional."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _contar(
        self,
        model: type,
        empresa_id: UUID,
        coluna: object | None = None,
        desde: datetime | None = None,
        ate: datetime | None = None,
    ) -> int:
        """Conta linhas do modelo filtradas por empresa e período."""
        condicoes: list = [model.empresa_id == empresa_id]  # type: ignore[attr-defined]
        if coluna is not None:
            _periodo(condicoes, coluna, desde, ate)
        stmt = select(func.count()).select_from(model).where(*condicoes)
        return int(self.session.execute(stmt).scalar_one())

    def _ids_conversas(
        self, empresa_id: UUID, desde: datetime | None, ate: datetime | None
    ) -> Select[tuple[UUID]]:
        """Subconsulta dos ids das conversas da empresa no período."""
        condicoes: list = [Conversation.empresa_id == empresa_id]
        _periodo(condicoes, Conversation.created_at, desde, ate)
        return select(Conversation.id).where(*condicoes)

    def _decisoes_vigentes(self, ids: Select[tuple[UUID]]) -> dict[UUID, str]:
        """Mapeia cada recomendação do período para a decisão vigente.

        O feedback é *append-only*; a última linha de cada recomendação vence.
        A recomendação pertence ao mesmo recorte de conversas dos demais KPIs,
        para que aceitas + descartadas nunca exceda o total de recomendações.
        """
        stmt = (
            select(Feedback.recommendation_id, Feedback.decisao)
            .join(Recommendation, Feedback.recommendation_id == Recommendation.id)
            .where(Recommendation.conversation_id.in_(ids))
            .order_by(Feedback.created_at, Feedback.id)
        )
        vigentes: dict[UUID, str] = {}
        for recomendacao_id, decisao in self.session.execute(stmt).all():
            vigentes[recomendacao_id] = decisao
        return vigentes

    def resumo(
        self,
        empresa_id: UUID,
        desde: datetime | None = None,
        ate: datetime | None = None,
    ) -> ResumoKpis:
        """Agrega os KPIs da empresa no período informado.

        Conversas, perguntas, recomendações e decisões respeitam o período
        (limites inclusivos), recortado pelo início da conversa; a cobertura de
        dados é o retrato atual do catálogo, sem recorte de período.
        """
        ids = self._ids_conversas(empresa_id, desde, ate)
        perguntas = int(
            self.session.execute(
                select(func.count())
                .select_from(Message)
                .where(Message.papel == "user", Message.conversation_id.in_(ids))
            ).scalar_one()
        )
        recomendacoes = int(
            self.session.execute(
                select(func.count())
                .select_from(Recommendation)
                .where(Recommendation.conversation_id.in_(ids))
            ).scalar_one()
        )
        decisoes = self._decisoes_vigentes(ids)
        return ResumoKpis(
            conversas=self._contar(
                Conversation, empresa_id, Conversation.created_at, desde, ate
            ),
            perguntas=perguntas,
            recomendacoes=recomendacoes,
            aceitas=sum(1 for decisao in decisoes.values() if decisao == "aceita"),
            descartadas=sum(
                1 for decisao in decisoes.values() if decisao == "descartada"
            ),
            itens_estoque=self._contar(StockItem, empresa_id),
            fornecedores=self._contar(Supplier, empresa_id),
            registros_transporte=self._contar(TransportRecord, empresa_id),
        )
