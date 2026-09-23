"""Testes unitários da geração determinística de sugestões."""

from __future__ import annotations

from uuid import uuid4

import pytest

from gestlog.correcoes.completude import (
    CampoCorrecaoInvalido,
    TipoCorrecaoInvalido,
    natureza,
)
from gestlog.correcoes.sugestoes import _ESTRATEGIAS, _FONTES, Sugestao, sugerir
from gestlog.db.models import StockItem, Supplier, TransportRecord


def _estoque(**campos: object) -> StockItem:
    base = {
        "empresa_id": uuid4(),
        "sku": f"SKU-{uuid4().hex[:6]}",
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
        "fornecedor_id": f"F-{uuid4().hex[:6]}",
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
        "codigo_rastreio": f"BR-{uuid4().hex[:6]}",
        "origem": "SP",
        "destino": "RJ",
        "peso_kg": 12.5,
        "status": "em_transito",
    }
    base.update(campos)
    return TransportRecord(**base)


_BUILDERS = {
    "estoque": _estoque,
    "fornecedores": _fornecedor,
    "transporte": _transporte,
}
_AUSENTE_POR_NATUREZA = {"texto": "", "inteiro": 0, "decimal": 0.0}


def test_moda_escolhe_valor_mais_frequente() -> None:
    alvo = _fornecedor(categoria="")
    demais = [
        _fornecedor(categoria="Insumos"),
        _fornecedor(categoria="Insumos"),
        _fornecedor(categoria="Serviços"),
    ]

    sugestao = sugerir("fornecedores", "categoria", alvo, [alvo, *demais])

    assert sugestao == Sugestao(
        campo="categoria",
        valor="Insumos",
        justificativa="Insumos é o valor mais frequente entre 3 registros do tenant",
        fonte="categoria mais comum entre 3 fornecedores",
    )


def test_moda_desempata_por_ordem_lexicografica() -> None:
    alvo = _estoque(local="")
    demais = [_estoque(local="B2"), _estoque(local="A1")]

    sugestao = sugerir("estoque", "local", alvo, [alvo, *demais])

    assert sugestao.valor == "A1"
    assert sugestao.fonte == "local mais comum nos itens"


def test_moda_ignora_vazios_e_o_proprio_alvo() -> None:
    alvo = _transporte(origem="")
    demais = [_transporte(origem="   "), _transporte(origem="Campinas")]

    sugestao = sugerir("transporte", "origem", alvo, [alvo, *demais])

    assert sugestao.valor == "Campinas"
    assert sugestao.fonte == "origem mais frequente nos registros"


def test_mediana_inteiro_com_quantidade_impar() -> None:
    alvo = _fornecedor(prazo_dias=0)
    demais = [
        _fornecedor(prazo_dias=9),
        _fornecedor(prazo_dias=5),
        _fornecedor(prazo_dias=7),
    ]

    sugestao = sugerir("fornecedores", "prazo_dias", alvo, [alvo, *demais])

    assert sugestao.valor == "7"
    assert sugestao.fonte == "prazo mediano dos fornecedores"
    assert (
        sugestao.justificativa
        == "mediana dos prazo_dias acima de zero entre 3 registros"
    )


def test_mediana_inteiro_com_quantidade_par_arredonda_para_cima() -> None:
    alvo = _estoque(minimo=0)
    demais = [_estoque(minimo=4), _estoque(minimo=5)]

    sugestao = sugerir("estoque", "minimo", alvo, [alvo, *demais])

    assert sugestao.valor == "5"
    assert sugestao.fonte == "estoque mínimo mediano dos itens"


def test_mediana_ignora_zeros_e_alvo() -> None:
    alvo = _estoque(minimo=0)
    demais = [_estoque(minimo=0), _estoque(minimo=0), _estoque(minimo=8)]

    sugestao = sugerir("estoque", "minimo", alvo, [alvo, *demais])

    assert sugestao.valor == "8"


def test_media_decimal_arredonda_para_uma_casa() -> None:
    alvo = _fornecedor(avaliacao=0.0)
    demais = [_fornecedor(avaliacao=4.0), _fornecedor(avaliacao=4.6)]

    sugestao = sugerir("fornecedores", "avaliacao", alvo, [alvo, *demais])

    assert sugestao.valor == "4.3"
    assert sugestao.fonte == "avaliação média dos fornecedores"
    assert (
        sugestao.justificativa == "média dos avaliacao acima de zero entre 2 registros"
    )


def test_media_decimal_meio_exato() -> None:
    alvo = _fornecedor(avaliacao=0.0)
    demais = [_fornecedor(avaliacao=4.0), _fornecedor(avaliacao=5.0)]

    sugestao = sugerir("fornecedores", "avaliacao", alvo, [alvo, *demais])

    assert sugestao.valor == "4.5"


def test_sem_base_quando_nao_ha_demais() -> None:
    alvo = _fornecedor(categoria="")

    sugestao = sugerir("fornecedores", "categoria", alvo, [alvo])

    assert sugestao.valor is None
    assert sugestao.fonte == ""
    assert sugestao.justificativa == "sem base de dados no tenant"


def test_sem_base_quando_demais_nao_tem_valor_positivo() -> None:
    alvo = _estoque(minimo=0)
    demais = [_estoque(minimo=0), _estoque(minimo=0)]

    sugestao = sugerir("estoque", "minimo", alvo, [alvo, *demais])

    assert sugestao.valor is None


@pytest.mark.parametrize(
    ("tipo", "campo"),
    [("fornecedores", "nome"), ("estoque", "nome"), ("transporte", "peso_kg")],
)
def test_campos_sem_estrategia_ficam_sem_sugestao(tipo: str, campo: str) -> None:
    alvo = _BUILDERS[tipo]()
    demais = [_BUILDERS[tipo](), _BUILDERS[tipo]()]

    sugestao = sugerir(tipo, campo, alvo, [alvo, *demais])

    assert sugestao.valor is None
    assert sugestao.fonte == ""


@pytest.mark.parametrize(
    ("tipo", "campo"),
    sorted((tipo, campo) for tipo, campos in _ESTRATEGIAS.items() for campo in campos),
)
def test_todo_campo_com_estrategia_gera_sugestao(tipo: str, campo: str) -> None:
    ausente = _AUSENTE_POR_NATUREZA[natureza(tipo, campo)]
    alvo = _BUILDERS[tipo](**{campo: ausente})
    demais = [_BUILDERS[tipo](), _BUILDERS[tipo]()]

    sugestao = sugerir(tipo, campo, alvo, [alvo, *demais])

    assert sugestao.valor is not None
    assert sugestao.fonte
    assert sugestao.justificativa


def test_estrategias_fontes_e_campos_sem_orfaos() -> None:
    com_estrategia = {
        (tipo, campo) for tipo, campos in _ESTRATEGIAS.items() for campo in campos
    }

    assert set(_FONTES) == com_estrategia
    for tipo, campo in com_estrategia:
        natureza(tipo, campo)


def test_sugerir_e_deterministica_para_os_mesmos_dados() -> None:
    alvo = _fornecedor(categoria="")
    demais = [_fornecedor(categoria="Insumos"), _fornecedor(categoria="Insumos")]

    primeira = sugerir("fornecedores", "categoria", alvo, [alvo, *demais])
    segunda = sugerir("fornecedores", "categoria", alvo, [alvo, *demais])

    assert primeira == segunda


def test_tipo_ou_campo_desconhecido_recusa() -> None:
    alvo = _estoque()

    with pytest.raises(TipoCorrecaoInvalido):
        sugerir("financeiro", "local", alvo, [alvo])
    with pytest.raises(CampoCorrecaoInvalido):
        sugerir("estoque", "quantidade", alvo, [alvo])
