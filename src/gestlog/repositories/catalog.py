"""Repositórios dos dados operacionais (estoque, fornecedores, transporte)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from gestlog.db.models import StockItem, Supplier, TransportRecord
from gestlog.repositories.base import EmpresaScopedRepository


class StockRepository(EmpresaScopedRepository[StockItem]):
    """Itens de estoque por empresa."""

    model = StockItem

    def get_by_sku(self, empresa_id: UUID, sku: str) -> StockItem | None:
        """Busca um item pelo SKU dentro do empresa."""
        stmt = select(StockItem).where(
            StockItem.empresa_id == empresa_id,
            StockItem.sku == sku.strip().upper(),
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        empresa_id: UUID,
        sku: str,
        nome: str,
        quantidade: int,
        minimo: int,
        local: str,
    ) -> StockItem:
        """Insere ou atualiza um item de estoque do empresa."""
        item = self.get_by_sku(empresa_id, sku)
        if item is None:
            return self.add(
                StockItem(
                    empresa_id=empresa_id,
                    sku=sku.strip().upper(),
                    nome=nome,
                    quantidade=quantidade,
                    minimo=minimo,
                    local=local,
                )
            )
        item.nome = nome
        item.quantidade = quantidade
        item.minimo = minimo
        item.local = local
        self.session.flush()
        return item


class SupplierRepository(EmpresaScopedRepository[Supplier]):
    """Fornecedores por empresa."""

    model = Supplier

    def get_by_fornecedor_id(
        self, empresa_id: UUID, fornecedor_id: str
    ) -> Supplier | None:
        """Busca um fornecedor pelo identificador dentro do empresa."""
        stmt = select(Supplier).where(
            Supplier.empresa_id == empresa_id,
            Supplier.fornecedor_id == fornecedor_id.strip().upper(),
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        empresa_id: UUID,
        fornecedor_id: str,
        nome: str,
        categoria: str,
        prazo_dias: int,
        avaliacao: float,
        ativo: bool,
    ) -> Supplier:
        """Insere ou atualiza um fornecedor do empresa."""
        fornecedor = self.get_by_fornecedor_id(empresa_id, fornecedor_id)
        if fornecedor is None:
            return self.add(
                Supplier(
                    empresa_id=empresa_id,
                    fornecedor_id=fornecedor_id.strip().upper(),
                    nome=nome,
                    categoria=categoria,
                    prazo_dias=prazo_dias,
                    avaliacao=avaliacao,
                    ativo=ativo,
                )
            )
        fornecedor.nome = nome
        fornecedor.categoria = categoria
        fornecedor.prazo_dias = prazo_dias
        fornecedor.avaliacao = avaliacao
        fornecedor.ativo = ativo
        self.session.flush()
        return fornecedor


class TransportRepository(EmpresaScopedRepository[TransportRecord]):
    """Registros de transporte por empresa."""

    model = TransportRecord

    def get_by_codigo(self, empresa_id: UUID, codigo: str) -> TransportRecord | None:
        """Busca um registro pelo código de rastreio dentro do empresa."""
        stmt = select(TransportRecord).where(
            TransportRecord.empresa_id == empresa_id,
            TransportRecord.codigo_rastreio == codigo.strip().upper(),
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        empresa_id: UUID,
        codigo_rastreio: str,
        origem: str,
        destino: str,
        peso_kg: float,
        status: str,
    ) -> TransportRecord:
        """Insere ou atualiza um registro de transporte do empresa."""
        registro = self.get_by_codigo(empresa_id, codigo_rastreio)
        if registro is None:
            return self.add(
                TransportRecord(
                    empresa_id=empresa_id,
                    codigo_rastreio=codigo_rastreio.strip().upper(),
                    origem=origem,
                    destino=destino,
                    peso_kg=peso_kg,
                    status=status,
                )
            )
        registro.origem = origem
        registro.destino = destino
        registro.peso_kg = peso_kg
        registro.status = status
        self.session.flush()
        return registro
