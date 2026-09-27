"""Testes unitários das regras de completude por tipo."""

from __future__ import annotations

from uuid import uuid4

import pytest

from gestlog.correcoes.completude import (
    CampoCorrecaoInvalido,
    TipoCorrecaoInvalido,
    campos_faltantes,
    valor_atual,
)
from gestlog.db.models import StockItem, Supplier, TransportRecord


def _estoque(**campos: object) -> StockItem:
    base = {
        "empresa_id": uuid4(),
        "sku": "SKU-1",
        "nome": "Parafuso",
        "quantidade": 0,
        "minimo": 10,
        "local": "A1",
    }
    base.update(campos)
    return StockItem(**base)


def _fornecedor(**campos: object) -> Supplier:
    base = {
        "empresa_id": uuid4(),
        "fornecedor_id": "F-1",
        "nome": "Fornecedor",
        "categoria": "Insumos",
        "prazo_dias": 7,
        "avaliacao": 4.5,
        "ativo": True,
    }
    base.update(campos)
    return Supplier(**base)


def _transporte(**campos: object) -> TransportRecord:
    base = {
        "empresa_id": uuid4(),
        "codigo_rastreio": "BR-1",
        "origem": "SP",
        "destino": "RJ",
        "peso_kg": 12.5,
        "status": "em_transito",
    }
    base.update(campos)
    return TransportRecord(**base)


def test_estoque_lista_todos_os_campos_faltantes_na_ordem_do_design() -> None:
    registro = _estoque(nome="  ", minimo=0, local="")

    assert campos_faltantes("estoque", registro) == ["nome", "minimo", "local"]


def test_estoque_marca_apenas_o_campo_ausente() -> None:
    registro = _estoque(nome="Parafuso", minimo=5, local="")

    assert campos_faltantes("estoque", registro) == ["local"]


def test_fornecedores_marcam_vazio_e_zero() -> None:
    registro = _fornecedor(nome="", categoria="  ", prazo_dias=0, avaliacao=0.0)

    assert campos_faltantes("fornecedores", registro) == [
        "nome",
        "categoria",
        "prazo_dias",
        "avaliacao",
    ]


def test_transporte_marca_vazio_e_zero() -> None:
    registro = _transporte(origem="", destino="", peso_kg=0.0, status=" ")

    assert campos_faltantes("transporte", registro) == [
        "origem",
        "destino",
        "peso_kg",
        "status",
    ]


def test_registro_completo_nao_tem_faltantes() -> None:
    assert campos_faltantes("estoque", _estoque()) == []
    assert campos_faltantes("fornecedores", _fornecedor()) == []
    assert campos_faltantes("transporte", _transporte()) == []


def test_zero_legitimo_e_booleano_nao_sao_ausentes() -> None:
    estoque = _estoque(quantidade=0, minimo=3)
    fornecedor = _fornecedor(ativo=False, avaliacao=0.1)
    transporte = _transporte(peso_kg=0.1)

    assert campos_faltantes("estoque", estoque) == []
    assert campos_faltantes("fornecedores", fornecedor) == []
    assert campos_faltantes("transporte", transporte) == []


def test_campos_de_identidade_e_contagem_nao_entram_na_completude() -> None:
    assert campos_faltantes("estoque", _estoque(sku="", quantidade=0, minimo=1)) == []
    assert (
        campos_faltantes("fornecedores", _fornecedor(fornecedor_id="", ativo=False))
        == []
    )
    assert (
        campos_faltantes("transporte", _transporte(codigo_rastreio="", status="ok"))
        == []
    )


def test_valor_atual_serializa_por_tipo_de_campo() -> None:
    registro = _fornecedor(nome="Fornecedor", prazo_dias=7, avaliacao=4.5)

    assert valor_atual("fornecedores", registro, "nome") == "Fornecedor"
    assert valor_atual("fornecedores", registro, "prazo_dias") == "7"
    assert valor_atual("fornecedores", registro, "avaliacao") == "4.5"


def test_valor_atual_serializa_ausente_de_forma_canonica() -> None:
    estoque = _estoque(nome="", minimo=0)
    transporte = _transporte(peso_kg=0)

    assert valor_atual("estoque", estoque, "nome") == ""
    assert valor_atual("estoque", estoque, "minimo") == "0"
    assert valor_atual("transporte", transporte, "peso_kg") == "0.0"


def test_tipo_desconhecido_recusa() -> None:
    with pytest.raises(TipoCorrecaoInvalido):
        campos_faltantes("financeiro", _estoque())
    with pytest.raises(TipoCorrecaoInvalido):
        valor_atual("financeiro", _estoque(), "nome")


def test_campo_desconhecido_recusa() -> None:
    with pytest.raises(CampoCorrecaoInvalido):
        valor_atual("estoque", _estoque(), "quantidade")
    with pytest.raises(CampoCorrecaoInvalido):
        valor_atual("estoque", _estoque(), "inexistente")
