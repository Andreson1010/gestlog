"""Repositórios dos dados operacionais (estoque, fornecedores, transporte)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from gestlog.db.models import StockItem, Supplier, TransportRecord
from gestlog.repositories.base import TenantScopedRepository


class StockRepository(TenantScopedRepository[StockItem]):
    """Itens de estoque por tenant."""

    model = StockItem

    def get_by_sku(self, tenant_id: UUID, sku: str) -> StockItem | None:
        """Busca um item pelo SKU dentro do tenant."""
        stmt = select(StockItem).where(
            StockItem.tenant_id == tenant_id,
            StockItem.sku == sku.strip().upper(),
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        tenant_id: UUID,
        sku: str,
        nome: str,
        quantidade: int,
        minimo: int,
        local: str,
    ) -> StockItem:
        """Insere ou atualiza um item de estoque do tenant."""
        item = self.get_by_sku(tenant_id, sku)
        if item is None:
            return self.add(
                StockItem(
                    tenant_id=tenant_id,
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


class SupplierRepository(TenantScopedRepository[Supplier]):
    """Fornecedores por tenant."""

    model = Supplier

    def get_by_fornecedor_id(
        self, tenant_id: UUID, fornecedor_id: str
    ) -> Supplier | None:
        """Busca um fornecedor pelo identificador dentro do tenant."""
        stmt = select(Supplier).where(
            Supplier.tenant_id == tenant_id,
            Supplier.fornecedor_id == fornecedor_id.strip().upper(),
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        tenant_id: UUID,
        fornecedor_id: str,
        nome: str,
        categoria: str,
        prazo_dias: int,
        avaliacao: float,
        ativo: bool,
    ) -> Supplier:
        """Insere ou atualiza um fornecedor do tenant."""
        fornecedor = self.get_by_fornecedor_id(tenant_id, fornecedor_id)
        if fornecedor is None:
            return self.add(
                Supplier(
                    tenant_id=tenant_id,
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


class TransportRepository(TenantScopedRepository[TransportRecord]):
    """Registros de transporte por tenant."""

    model = TransportRecord

    def get_by_codigo(self, tenant_id: UUID, codigo: str) -> TransportRecord | None:
        """Busca um registro pelo código de rastreio dentro do tenant."""
        stmt = select(TransportRecord).where(
            TransportRecord.tenant_id == tenant_id,
            TransportRecord.codigo_rastreio == codigo.strip().upper(),
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def upsert(
        self,
        tenant_id: UUID,
        codigo_rastreio: str,
        origem: str,
        destino: str,
        peso_kg: float,
        status: str,
    ) -> TransportRecord:
        """Insere ou atualiza um registro de transporte do tenant."""
        registro = self.get_by_codigo(tenant_id, codigo_rastreio)
        if registro is None:
            return self.add(
                TransportRecord(
                    tenant_id=tenant_id,
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
