"""Serviço da fila de correções: materializa itens pendentes de forma idempotente."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from gestlog.correcoes.completude import Registro, campos_faltantes, valor_atual
from gestlog.correcoes.sugestoes import sugerir
from gestlog.db.models import ItemCorrecao
from gestlog.repositories.base import EmpresaScopedRepository
from gestlog.repositories.catalog import (
    StockRepository,
    SupplierRepository,
    TransportRepository,
)
from gestlog.repositories.correcoes import CorrectionRepository

_FONTES_CADASTRO: dict[str, tuple[type[EmpresaScopedRepository], str]] = {
    "estoque": (StockRepository, "sku"),
    "fornecedores": (SupplierRepository, "fornecedor_id"),
    "transporte": (TransportRepository, "codigo_rastreio"),
}


@dataclass(frozen=True)
class CorrectionService:
    """Materializa e lista os itens de correção cadastral de uma empresa."""

    session: Session
    empresa_id: UUID

    def gerar_fila(self) -> list[ItemCorrecao]:
        """Cria itens pendentes para campos faltantes ainda sem item.

        Idempotente: um item aberto para o alvo/campo — ou um item terminal com o
        mesmo ``valor_no_pedido`` — impede a recriação. Commita ao final.
        """
        repo = CorrectionRepository(self.session)
        criados: list[ItemCorrecao] = []
        for tipo, (fabrica, chave) in _FONTES_CADASTRO.items():
            registros = fabrica(self.session).list(self.empresa_id)
            for registro in registros:
                criados.extend(
                    self._materializar(repo, tipo, chave, registro, registros)
                )
        self.session.commit()
        return criados

    def listar(
        self, status: str = "pendente", limite: int | None = None
    ) -> list[ItemCorrecao]:
        """Lista os itens do tenant com o status, opcionalmente limitados."""
        return CorrectionRepository(self.session).list_by_status(
            self.empresa_id, status, limite
        )

    def _materializar(
        self,
        repo: CorrectionRepository,
        tipo: str,
        chave: str,
        registro: Registro,
        registros: Sequence[Registro],
    ) -> list[ItemCorrecao]:
        """Cria os itens dos campos faltantes do registro que ainda não existem."""
        alvo_chave = str(getattr(registro, chave) or "").strip().upper()
        criados: list[ItemCorrecao] = []
        for campo in campos_faltantes(tipo, registro):
            valor_no_pedido = valor_atual(tipo, registro, campo)
            if repo.abertos_para(self.empresa_id, tipo, alvo_chave, campo):
                continue
            if repo.existe_para(
                self.empresa_id, tipo, alvo_chave, campo, valor_no_pedido
            ):
                continue
            sugestao = sugerir(tipo, campo, registro, registros)
            item = ItemCorrecao(
                empresa_id=self.empresa_id,
                tipo=tipo,
                alvo_chave=alvo_chave,
                campo=campo,
                valor_no_pedido=valor_no_pedido,
                valor_sugerido=sugestao.valor,
                justificativa=sugestao.justificativa,
                fonte=sugestao.fonte,
                status="pendente",
            )
            criados.append(repo.add(item))
        return criados
