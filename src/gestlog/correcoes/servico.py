"""Serviço da fila de correções: materializa, decide e aplica com auditoria."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from gestlog.audit import (
    EVENTO_CORRECAO_APLICADA,
    EVENTO_CORRECAO_APROVADA,
    EVENTO_CORRECAO_FALHOU,
    registrar_evento,
)
from gestlog.correcoes.completude import (
    Registro,
    campos_faltantes,
    natureza,
    valor_atual,
)
from gestlog.correcoes.erros import (
    CorrecaoAlvoInvalido,
    CorrecaoFalhaEscrita,
    CorrecaoNaoAprovavel,
    CorrecaoNaoEncontrada,
)
from gestlog.correcoes.sugestoes import sugerir
from gestlog.db.models import ItemCorrecao
from gestlog.repositories.base import EmpresaScopedRepository
from gestlog.repositories.catalog import (
    StockRepository,
    SupplierRepository,
    TransportRepository,
)
from gestlog.repositories.correcoes import CorrectionRepository

_FONTES_CADASTRO: dict[str, tuple[type[EmpresaScopedRepository], str, str]] = {
    "estoque": (StockRepository, "sku", "get_by_sku"),
    "fornecedores": (SupplierRepository, "fornecedor_id", "get_by_fornecedor_id"),
    "transporte": (TransportRepository, "codigo_rastreio", "get_by_codigo"),
}

_CAMPOS_UPSERT: dict[str, tuple[str, ...]] = {
    "estoque": ("sku", "nome", "quantidade", "minimo", "local"),
    "fornecedores": (
        "fornecedor_id",
        "nome",
        "categoria",
        "prazo_dias",
        "avaliacao",
        "ativo",
    ),
    "transporte": ("codigo_rastreio", "origem", "destino", "peso_kg", "status"),
}

MOTIVO_ALVO_AUSENTE = "registro alvo inexistente"
MOTIVO_CONFLITO = "registro alterado após a sugestão"
MOTIVO_ERRO_ESCRITA = "erro ao aplicar a correção"

_LIMITE_VALOR_AUDITORIA = 255


def _converter(natureza_campo: str, valor: str | None) -> object:
    """Converte a string canônica da sugestão para o tipo da coluna."""
    if natureza_campo == "inteiro":
        return int(valor or 0)
    if natureza_campo == "decimal":
        return float(valor or 0.0)
    return "" if valor is None else str(valor)


def _valor_auditavel(valor: str | None) -> str | None:
    """Trunca o valor de catálogo antes de levá-lo ao detalhe de auditoria.

    O valor completo permanece no item (``valor_sugerido``), referenciável por
    ``item_id``; a auditoria carrega apenas o recorte operacional (ESC-06).
    """
    if valor is None:
        return None
    return valor[:_LIMITE_VALOR_AUDITORIA]


@dataclass(frozen=True)
class CorrectionService:
    """Materializa, lista e decide os itens de correção de uma empresa."""

    session: Session
    empresa_id: UUID

    def gerar_fila(self) -> list[ItemCorrecao]:
        """Cria itens pendentes para campos faltantes ainda sem item.

        Idempotente: um item aberto para o alvo/campo — ou um item terminal com o
        mesmo ``valor_no_pedido`` — impede a recriação. Commita ao final.
        """
        repo = CorrectionRepository(self.session)
        criados: list[ItemCorrecao] = []
        for tipo, (fabrica, chave, _) in _FONTES_CADASTRO.items():
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

    def aprovar(self, item_id: UUID, user_id: UUID, papel: str) -> ItemCorrecao:
        """Aprova, aplica e audita um item pendente, restrito ao tenant.

        Recusa com ``CorrecaoNaoEncontrada`` (404 cross-tenant), com
        ``CorrecaoNaoAprovavel`` (409 terminal/sem sugestão) ou
        ``CorrecaoAlvoInvalido`` (409 alvo ausente/alterado, encerrando o item
        como ``falhou`` sem escrita). A escrita e a auditoria ocorrem na mesma
        transação; uma exceção na aplicação faz rollback e marca ``falhou``.
        """
        item = CorrectionRepository(self.session).get(self.empresa_id, item_id)
        if item is None:
            raise CorrecaoNaoEncontrada()
        self._validar_pendente(item)
        registro = self._resolver_alvo(item)
        if registro is None:
            self._falhar(item, MOTIVO_ALVO_AUSENTE, user_id, papel)
            raise CorrecaoAlvoInvalido(MOTIVO_ALVO_AUSENTE)
        atual = valor_atual(item.tipo, registro, item.campo)
        if atual != item.valor_no_pedido:
            self._falhar(item, MOTIVO_CONFLITO, user_id, papel)
            raise CorrecaoAlvoInvalido(MOTIVO_CONFLITO)
        return self._aplicar(item, registro, user_id, papel, atual)

    def _validar_pendente(self, item: ItemCorrecao) -> None:
        """Recusa itens terminais ou sem sugestão, sem alterar o estado."""
        if item.status != "pendente":
            raise CorrecaoNaoAprovavel("item já decidido")
        if item.valor_sugerido is None:
            raise CorrecaoNaoAprovavel("item sem sugestão")

    def _resolver_alvo(self, item: ItemCorrecao) -> Registro | None:
        """Resolve o registro alvo pelo ``alvo_chave`` dentro da empresa."""
        if item.tipo not in _FONTES_CADASTRO:
            raise CorrecaoNaoAprovavel("tipo de correção desconhecido")
        fabrica, _, metodo = _FONTES_CADASTRO[item.tipo]
        buscar = getattr(fabrica(self.session), metodo)
        return buscar(self.empresa_id, item.alvo_chave)

    def _aplicar(
        self,
        item: ItemCorrecao,
        registro: Registro,
        user_id: UUID,
        papel: str,
        atual: str,
    ) -> ItemCorrecao:
        """Registra a decisão, aplica (ou no-op) e finaliza com auditoria."""
        self._decidir(item, user_id, papel)
        if item.valor_sugerido != atual:
            try:
                self._escrever(item, registro)
            except Exception as erro:
                self._falhar_apos_erro(item.id, user_id, papel)
                raise CorrecaoFalhaEscrita(MOTIVO_ERRO_ESCRITA) from erro
        return self._finalizar(item, user_id)

    def _escrever(self, item: ItemCorrecao, registro: Registro) -> None:
        """Sobrepõe apenas o campo corrigido e chama o ``upsert`` do tipo."""
        natureza_campo = natureza(item.tipo, item.campo)
        setattr(registro, item.campo, _converter(natureza_campo, item.valor_sugerido))
        fabrica, _, _ = _FONTES_CADASTRO[item.tipo]
        valores = [getattr(registro, nome) for nome in _CAMPOS_UPSERT[item.tipo]]
        fabrica(self.session).upsert(self.empresa_id, *valores)

    def _decidir(self, item: ItemCorrecao, user_id: UUID, papel: str) -> None:
        """Marca a decisão de aprovação com autor, papel e timestamp."""
        item.status = "aprovado"
        item.decidido_por = user_id
        item.papel_aprovador = papel
        item.decidido_em = datetime.now(UTC)

    def _finalizar(self, item: ItemCorrecao, user_id: UUID) -> ItemCorrecao:
        """Marca o item aplicado, audita e confirma a transação."""
        item.status = "aplicado"
        item.aplicado_em = datetime.now(UTC)
        base = {
            "item_id": str(item.id),
            "tipo": item.tipo,
            "alvo_chave": item.alvo_chave,
            "campo": item.campo,
        }
        registrar_evento(
            self.session,
            self.empresa_id,
            EVENTO_CORRECAO_APROVADA,
            user_id,
            detalhe=base,
        )
        registrar_evento(
            self.session,
            self.empresa_id,
            EVENTO_CORRECAO_APLICADA,
            user_id,
            detalhe={**base, "valor": _valor_auditavel(item.valor_sugerido)},
        )
        self.session.commit()
        return item

    def _falhar(
        self, item: ItemCorrecao, motivo: str, user_id: UUID, papel: str
    ) -> None:
        """Encerra o item como falha, audita e confirma a transação."""
        item.status = "falhou"
        item.motivo_falha = motivo
        item.decidido_por = user_id
        item.papel_aprovador = papel
        item.decidido_em = datetime.now(UTC)
        registrar_evento(
            self.session,
            self.empresa_id,
            EVENTO_CORRECAO_FALHOU,
            user_id,
            detalhe={"item_id": str(item.id), "motivo": motivo},
        )
        self.session.commit()

    def _falhar_apos_erro(self, item_id: UUID, user_id: UUID, papel: str) -> None:
        """Desfaz a escrita parcial e marca a falha numa transação nova."""
        self.session.rollback()
        item = CorrectionRepository(self.session).get(self.empresa_id, item_id)
        if item is not None:
            self._falhar(item, MOTIVO_ERRO_ESCRITA, user_id, papel)

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
