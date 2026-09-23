"""Repositório da fila de correções cadastrais com escopo de empresa."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select

from gestlog.db.models import ItemCorrecao
from gestlog.repositories.base import EmpresaScopedRepository

_STATUS_ABERTOS = ("pendente", "aprovado")
_STATUS_TERMINAIS = ("rejeitado", "aplicado", "falhou")
_STATUS_TRILHA = ("aplicado", "falhou")


class CorrectionRepository(EmpresaScopedRepository[ItemCorrecao]):
    """Itens de correção por empresa, com busca de dedup e de trilha."""

    model = ItemCorrecao

    def list_by_status(
        self, empresa_id: UUID, status: str, limite: int | None = None
    ) -> list[ItemCorrecao]:
        """Lista os itens da empresa com o status, em ordem de criação.

        ``limite`` restringe o volume retornado (paginação); sem ele, lista tudo.
        """
        stmt = (
            select(ItemCorrecao)
            .where(
                ItemCorrecao.empresa_id == empresa_id,
                ItemCorrecao.status == status,
            )
            .order_by(ItemCorrecao.created_at, ItemCorrecao.id)
        )
        if limite is not None:
            stmt = stmt.limit(limite)
        return list(self.session.execute(stmt).scalars().all())

    def existe_para(
        self,
        empresa_id: UUID,
        tipo: str,
        alvo_chave: str,
        campo: str,
        valor_no_pedido: str,
    ) -> bool:
        """Verifica se já existe item para o alvo, campo e valor informados."""
        stmt = select(ItemCorrecao.id).where(
            ItemCorrecao.empresa_id == empresa_id,
            ItemCorrecao.tipo == tipo,
            ItemCorrecao.alvo_chave == alvo_chave,
            ItemCorrecao.campo == campo,
            ItemCorrecao.valor_no_pedido == valor_no_pedido,
        )
        return self.session.execute(stmt).first() is not None

    def abertos_para(
        self, empresa_id: UUID, tipo: str, alvo_chave: str, campo: str
    ) -> list[ItemCorrecao]:
        """Lista os itens abertos (``pendente``/``aprovado``) do alvo e campo."""
        stmt = (
            select(ItemCorrecao)
            .where(
                ItemCorrecao.empresa_id == empresa_id,
                ItemCorrecao.tipo == tipo,
                ItemCorrecao.alvo_chave == alvo_chave,
                ItemCorrecao.campo == campo,
                ItemCorrecao.status.in_(_STATUS_ABERTOS),
            )
            .order_by(ItemCorrecao.created_at, ItemCorrecao.id)
        )
        return list(self.session.execute(stmt).scalars().all())

    def listar_trilha(
        self,
        empresa_id: UUID,
        desde: datetime | None = None,
        ate: datetime | None = None,
        limite: int | None = None,
    ) -> list[ItemCorrecao]:
        """Lista as correções de fato aplicadas no período, recentes primeiro.

        Cobre apenas ``aplicado``/``falhou`` (a tentativa de escrita de uma
        correção); ``rejeitado`` é terminal, porém não gerou escrita e fica fora
        da trilha de correções aplicadas da P2. Filtra ``decidido_em`` de forma
        inclusiva por ``desde``/``ate`` quando informados e limita o volume por
        ``limite``.
        """
        condicoes = [
            ItemCorrecao.empresa_id == empresa_id,
            ItemCorrecao.status.in_(_STATUS_TRILHA),
        ]
        if desde is not None:
            condicoes.append(ItemCorrecao.decidido_em >= desde)
        if ate is not None:
            condicoes.append(ItemCorrecao.decidido_em <= ate)
        stmt = (
            select(ItemCorrecao)
            .where(*condicoes)
            .order_by(ItemCorrecao.decidido_em.desc(), ItemCorrecao.id)
        )
        if limite is not None:
            stmt = stmt.limit(limite)
        return list(self.session.execute(stmt).scalars().all())

    def purgar_expiradas(self, empresa_id: UUID, limite: datetime) -> int:
        """Apaga os itens decididos da empresa anteriores a ``limite``.

        Itens operacionais (``pendente``/``aprovado``) nunca são removidos;
        devolve a quantidade de itens apagados.
        """
        stmt = select(ItemCorrecao.id).where(
            ItemCorrecao.empresa_id == empresa_id,
            ItemCorrecao.status.in_(_STATUS_TERMINAIS),
            ItemCorrecao.created_at < limite,
        )
        ids = list(self.session.execute(stmt).scalars().all())
        if not ids:
            return 0
        self.session.execute(delete(ItemCorrecao).where(ItemCorrecao.id.in_(ids)))
        return len(ids)
