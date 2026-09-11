"""Testes das ferramentas de domínio."""

from __future__ import annotations

from gestlog.tools.inventory import (
    calcular_reposicao,
    consultar_estoque,
    listar_movimentacoes,
)
from gestlog.tools.suppliers import (
    avaliar_desempenho,
    consultar_fornecedor,
    listar_fornecedores,
)
from gestlog.tools.transport import calcular_frete, consultar_prazo, rastrear_entrega


def test_transport_tools() -> None:
    frete = calcular_frete.invoke(
        {"origem": "Sao Paulo", "destino": "Curitiba", "peso_kg": 10.0}
    )
    assert "R$" in frete
    assert "Prazo" in consultar_prazo.invoke(
        {"origem": "Sao Paulo", "destino": "Salvador"}
    )
    assert "GL-1001" in rastrear_entrega.invoke({"codigo": "GL-1001"})
    assert "não encontrado" in rastrear_entrega.invoke({"codigo": "XXX"})


def test_supplier_tools() -> None:
    assert "TransLog" in listar_fornecedores.invoke({"categoria": "transporte"})
    assert "Nenhum" in listar_fornecedores.invoke({"categoria": "inexistente"})
    assert "ativo" in consultar_fornecedor.invoke({"fornecedor_id": "F-001"})
    assert "não encontrado" in consultar_fornecedor.invoke({"fornecedor_id": "F-999"})
    assert "atrasos" in avaliar_desempenho.invoke({"fornecedor_id": "F-002"})
    assert "não encontrado" in avaliar_desempenho.invoke({"fornecedor_id": "F-999"})


def test_inventory_tools() -> None:
    assert "SKU-100" in consultar_estoque.invoke({"sku": "sku-100"})
    assert "não encontrado" in consultar_estoque.invoke({"sku": "SKU-999"})
    assert "reposição sugerida" in calcular_reposicao.invoke(
        {"sku": "SKU-200", "consumo_medio_dia": 10}
    )
    assert "maior que zero" in calcular_reposicao.invoke(
        {"sku": "SKU-200", "consumo_medio_dia": 0}
    )
    assert "não encontrado" in calcular_reposicao.invoke(
        {"sku": "SKU-999", "consumo_medio_dia": 5}
    )
    assert "SKU-300" in listar_movimentacoes.invoke({"sku": "SKU-300"})
    assert "não encontrado" in listar_movimentacoes.invoke({"sku": "SKU-999"})
