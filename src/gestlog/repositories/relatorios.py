"""Agregações de relatórios operacionais por domínio (REL-06..REL-18)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from gestlog.db.models import CatalogoHistorico
from gestlog.repositories.historico import HistoricoRepository

_FATOR_EXCEDENTE = 2


@dataclass(frozen=True)
class ItemEstoque:
    """Item de estoque vigente no período."""

    chave: str
    nome: str
    categoria: str
    local: str
    quantidade: int
    minimo: int

    @property
    def situacao(self) -> str:
        """Classifica o item em abaixo do mínimo, excedente ou normal."""
        if self.quantidade < self.minimo:
            return "Abaixo do mínimo"
        if self.minimo > 0 and self.quantidade > self.minimo * _FATOR_EXCEDENTE:
            return "Excedente"
        return "Normal"


@dataclass(frozen=True)
class ResumoEstoque:
    """Itens de estoque vigentes e contagens por local e categoria."""

    itens: tuple[ItemEstoque, ...] = ()
    por_local: tuple[tuple[str, int], ...] = ()
    por_categoria: tuple[tuple[str, int], ...] = ()

    @property
    def abaixo_minimo(self) -> tuple[ItemEstoque, ...]:
        """Itens com quantidade abaixo do mínimo."""
        return tuple(item for item in self.itens if item.situacao == "Abaixo do mínimo")

    @property
    def excedentes(self) -> tuple[ItemEstoque, ...]:
        """Itens com quantidade acima do dobro do mínimo."""
        return tuple(item for item in self.itens if item.situacao == "Excedente")


@dataclass(frozen=True)
class RegistroTransporte:
    """Registro de transporte vigente no período."""

    chave: str
    origem: str
    destino: str
    peso_kg: float
    status: str
    previsao_entrega: datetime | None = None
    data_entrega: datetime | None = None

    @property
    def rota(self) -> str:
        """Rota no formato ``origem → destino``."""
        return f"{self.origem} → {self.destino}"

    @property
    def atrasado(self) -> bool:
        """Indica entrega após a previsão (ambas as datas preenchidas)."""
        if self.previsao_entrega is None or self.data_entrega is None:
            return False
        return self.data_entrega > self.previsao_entrega

    @property
    def situacao(self) -> str:
        """Situação do registro: ``Atrasado`` ou ``No prazo``."""
        return "Atrasado" if self.atrasado else "No prazo"


@dataclass(frozen=True)
class ResumoTransporte:
    """Registros de transporte vigentes e agregações por status e rota."""

    registros: tuple[RegistroTransporte, ...] = ()
    por_status: tuple[tuple[str, int], ...] = ()
    peso_por_rota: tuple[tuple[str, float], ...] = ()

    @property
    def atrasos(self) -> int:
        """Quantidade de registros entregues após a previsão."""
        return sum(1 for registro in self.registros if registro.atrasado)


@dataclass(frozen=True)
class Fornecedor:
    """Fornecedor vigente no período."""

    chave: str
    nome: str
    categoria: str
    prazo_dias: int
    avaliacao: float
    ativo: bool

    @property
    def situacao(self) -> str:
        """Situação do fornecedor: ``Ativo`` ou ``Inativo``."""
        return "Ativo" if self.ativo else "Inativo"


@dataclass(frozen=True)
class ResumoFornecedores:
    """Fornecedores vigentes, indicadores e contagem por categoria."""

    fornecedores: tuple[Fornecedor, ...] = ()
    por_categoria: tuple[tuple[str, int], ...] = ()
    avaliacao_media: float = 0.0
    prazo_medio: float = 0.0

    @property
    def ativos(self) -> int:
        """Quantidade de fornecedores ativos."""
        return sum(1 for fornecedor in self.fornecedores if fornecedor.ativo)

    @property
    def inativos(self) -> int:
        """Quantidade de fornecedores inativos."""
        return sum(1 for fornecedor in self.fornecedores if not fornecedor.ativo)


class RelatorioRepository:
    """Agrega o histórico versionado por domínio, período e empresa."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._historico = HistoricoRepository(session)

    def estoque(
        self,
        empresa_id: UUID,
        desde: datetime | None = None,
        ate: datetime | None = None,
    ) -> ResumoEstoque:
        """Resume o estoque vigente no período, por local e categoria."""
        base = self._historico.ultimo_por_chave(empresa_id, "estoque", desde, ate)
        itens = tuple(_item_estoque(linha) for linha in self._listar(base))
        return ResumoEstoque(
            itens=itens,
            por_local=self._contagens(base, "local"),
            por_categoria=self._contagens(base, "categoria"),
        )

    def transporte(
        self,
        empresa_id: UUID,
        desde: datetime | None = None,
        ate: datetime | None = None,
    ) -> ResumoTransporte:
        """Resume o transporte vigente no período, por status e rota."""
        base = self._historico.ultimo_por_chave(empresa_id, "transporte", desde, ate)
        registros = tuple(_registro_transporte(linha) for linha in self._listar(base))
        return ResumoTransporte(
            registros=registros,
            por_status=self._contagens(base, "status"),
            peso_por_rota=self._peso_por_rota(base),
        )

    def fornecedores(
        self,
        empresa_id: UUID,
        desde: datetime | None = None,
        ate: datetime | None = None,
    ) -> ResumoFornecedores:
        """Resume os fornecedores vigentes no período e seus indicadores."""
        base = self._historico.ultimo_por_chave(empresa_id, "fornecedores", desde, ate)
        fornecedores = tuple(_fornecedor(linha) for linha in self._listar(base))
        avaliacao_media, prazo_medio = self._medias(base)
        return ResumoFornecedores(
            fornecedores=fornecedores,
            por_categoria=self._contagens(base, "categoria"),
            avaliacao_media=avaliacao_media,
            prazo_medio=prazo_medio,
        )

    def _listar(
        self, base: Select[tuple[CatalogoHistorico]]
    ) -> list[CatalogoHistorico]:
        """Materializa as linhas vigentes do histórico, ordenadas por chave."""
        stmt = base.order_by(CatalogoHistorico.chave)
        return list(self.session.execute(stmt).scalars().all())

    def _contagens(
        self, base: Select[tuple[CatalogoHistorico]], coluna: str
    ) -> tuple[tuple[str, int], ...]:
        """Conta as linhas vigentes agrupadas por uma coluna (GROUP BY)."""
        sub = base.subquery()
        alvo = sub.c[coluna]
        stmt = select(alvo, func.count()).group_by(alvo).order_by(alvo)
        return tuple(
            (str(valor or ""), int(total))
            for valor, total in self.session.execute(stmt).all()
        )

    def _peso_por_rota(
        self, base: Select[tuple[CatalogoHistorico]]
    ) -> tuple[tuple[str, float], ...]:
        """Soma o peso por rota (``origem``, ``destino``), incluindo zero."""
        sub = base.subquery()
        stmt = (
            select(sub.c.origem, sub.c.destino, func.sum(sub.c.peso_kg))
            .group_by(sub.c.origem, sub.c.destino)
            .order_by(sub.c.origem, sub.c.destino)
        )
        return tuple(
            (f"{origem or ''} → {destino or ''}", float(total or 0.0))
            for origem, destino, total in self.session.execute(stmt).all()
        )

    def _medias(self, base: Select[tuple[CatalogoHistorico]]) -> tuple[float, float]:
        """Calcula as médias de avaliação e prazo dos fornecedores vigentes."""
        sub = base.subquery()
        stmt = select(func.avg(sub.c.avaliacao), func.avg(sub.c.prazo_dias))
        avaliacao, prazo = self.session.execute(stmt).one()
        return float(avaliacao or 0.0), float(prazo or 0.0)


def _item_estoque(linha: CatalogoHistorico) -> ItemEstoque:
    """Converte uma linha do histórico em item de estoque."""
    return ItemEstoque(
        chave=linha.chave,
        nome=linha.nome or "",
        categoria=linha.categoria or "",
        local=linha.local or "",
        quantidade=int(linha.quantidade or 0),
        minimo=int(linha.minimo or 0),
    )


def _registro_transporte(linha: CatalogoHistorico) -> RegistroTransporte:
    """Converte uma linha do histórico em registro de transporte."""
    return RegistroTransporte(
        chave=linha.chave,
        origem=linha.origem or "",
        destino=linha.destino or "",
        peso_kg=float(linha.peso_kg or 0.0),
        status=linha.status or "",
        previsao_entrega=linha.previsao_entrega,
        data_entrega=linha.data_entrega,
    )


def _fornecedor(linha: CatalogoHistorico) -> Fornecedor:
    """Converte uma linha do histórico em fornecedor."""
    return Fornecedor(
        chave=linha.chave,
        nome=linha.nome or "",
        categoria=linha.categoria or "",
        prazo_dias=int(linha.prazo_dias or 0),
        avaliacao=float(linha.avaliacao or 0.0),
        ativo=bool(linha.ativo),
    )
