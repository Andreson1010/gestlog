"""Histórico versionado de snapshots de catálogo por importação."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session

from gestlog.db.models import CatalogoHistorico, ImportJob


class HistoricoRepository:
    """Escrita e leitura dos snapshots versionados de catálogo.

    O histórico é *append-only*: cada importação aceita grava uma linha por
    registro; a leitura devolve o último snapshot de cada ``chave`` no período
    (limites inclusivos), sem N+1.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def registrar(
        self, job: ImportJob, dominio: str, chave: str, **payload: object
    ) -> CatalogoHistorico:
        """Grava o snapshot de um registro aceito, ligado à importação."""
        snapshot = CatalogoHistorico(
            empresa_id=job.empresa_id,
            dominio=dominio,
            chave=chave.strip().upper(),
            import_job_id=job.id,
            importado_em=job.created_at,
            **payload,
        )
        self.session.add(snapshot)
        self.session.flush()
        return snapshot

    def ultimo_por_chave(
        self,
        empresa_id: UUID,
        dominio: str,
        desde: datetime | None = None,
        ate: datetime | None = None,
    ) -> Select[tuple[CatalogoHistorico]]:
        """Seleciona o último snapshot de cada chave no período (inclusivo).

        Devolve **uma linha por ``chave``**. O vencedor é o snapshot mais
        recente por ``importado_em``; empates de timestamp (duas linhas com a
        mesma chave aceitas na mesma importação, que gravam o mesmo
        ``job.created_at``) são desempatados pelo maior ``id``. Sem o desempate
        o ``JOIN`` casaria as duas linhas e duplicaria a tabela e os agregados.
        """
        condicoes = self._condicoes(empresa_id, dominio, desde, ate)
        recentes = (
            select(
                CatalogoHistorico.id.label("id"),
                func.row_number()
                .over(
                    partition_by=CatalogoHistorico.chave,
                    order_by=(
                        CatalogoHistorico.importado_em.desc(),
                        CatalogoHistorico.id.desc(),
                    ),
                )
                .label("posicao"),
            )
            .where(*condicoes)
            .subquery()
        )
        return (
            select(CatalogoHistorico)
            .join(recentes, recentes.c.id == CatalogoHistorico.id)
            .where(recentes.c.posicao == 1)
        )

    @staticmethod
    def _condicoes(
        empresa_id: UUID,
        dominio: str,
        desde: datetime | None,
        ate: datetime | None,
    ) -> list[ColumnElement[bool]]:
        """Monta os filtros de empresa, domínio e período inclusivo."""
        condicoes: list[ColumnElement[bool]] = [
            CatalogoHistorico.empresa_id == empresa_id,
            CatalogoHistorico.dominio == dominio,
        ]
        if desde is not None:
            condicoes.append(CatalogoHistorico.importado_em >= desde)
        if ate is not None:
            condicoes.append(CatalogoHistorico.importado_em <= ate)
        return condicoes
