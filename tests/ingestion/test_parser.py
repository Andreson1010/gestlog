"""Testes unitários dos parsers e validadores de importação (T11)."""

from __future__ import annotations

from io import BytesIO

import pytest
from openpyxl import Workbook

from gestlog.ingestion import (
    ArquivoVazio,
    ColunasFaltando,
    ErroLinha,
    FormatoArquivoInvalido,
    RegistroEstoque,
    RegistroFornecedor,
    RegistroTransporte,
    TipoImportacaoInvalido,
    analisar,
)


def _csv(texto: str) -> bytes:
    return texto.encode("utf-8")


def _xlsx(linhas: list[list[object]]) -> bytes:
    planilha = Workbook()
    aba = planilha.active
    for linha in linhas:
        aba.append(linha)
    buffer = BytesIO()
    planilha.save(buffer)
    return buffer.getvalue()


def test_estoque_csv_normaliza() -> None:
    conteudo = _csv(
        "sku,nome,quantidade,minimo,local\n"
        "sku-1,Caixa grande,10,2,A1\n"
        "SKU-2,Pallet,0,1,\n"
    )

    resultado = analisar("estoque", conteudo, "estoque.csv")

    assert resultado.aceitas == 2
    assert resultado.rejeitadas == 0
    assert resultado.registros[0] == RegistroEstoque(
        sku="SKU-1", nome="Caixa grande", quantidade=10, minimo=2, local="A1"
    )
    assert resultado.registros[1].local == ""


def test_cabecalho_aceita_maiusculas_espacos_e_ordem_diferente() -> None:
    conteudo = _csv(" Nome , SKU ,Quantidade,Minimo\nCaixa,SKU-1,5,1\n")

    resultado = analisar("estoque", conteudo, "estoque.csv")

    assert resultado.aceitas == 1
    assert resultado.registros[0].sku == "SKU-1"


def test_fornecedores_normaliza_booleano_e_decimal_com_virgula() -> None:
    conteudo = _csv(
        "fornecedor_id,nome,categoria,prazo_dias,avaliacao,ativo\n"
        "f-1,TransLog,transporte,5,4.5,sim\n"
        'f-2,RodoVeloz,,0,"3,0",não\n'
    )

    resultado = analisar("fornecedores", conteudo, "fornecedores.csv")

    assert resultado.aceitas == 2
    assert resultado.registros[0] == RegistroFornecedor(
        fornecedor_id="F-1",
        nome="TransLog",
        categoria="transporte",
        prazo_dias=5,
        avaliacao=4.5,
        ativo=True,
    )
    assert resultado.registros[1].ativo is False
    assert resultado.registros[1].avaliacao == 3.0


def test_transporte_normaliza() -> None:
    conteudo = _csv(
        "codigo_rastreio,origem,destino,peso_kg,status\n"
        "gl-1,SP,CWB,12.5,em trânsito\n"
    )

    resultado = analisar("transporte", conteudo, "transporte.csv")

    assert resultado.registros == (
        RegistroTransporte(
            codigo_rastreio="GL-1",
            origem="SP",
            destino="CWB",
            peso_kg=12.5,
            status="em trânsito",
        ),
    )


def test_csv_com_ponto_e_virgula_e_lido() -> None:
    conteudo = _csv("sku;nome;quantidade;minimo\nSKU-1;Caixa;5;1\n")

    resultado = analisar("estoque", conteudo, "estoque.csv")

    assert resultado.aceitas == 1
    assert resultado.registros[0].quantidade == 5


def test_xlsx_e_lido() -> None:
    conteudo = _xlsx(
        [
            ["sku", "nome", "quantidade", "minimo"],
            ["SKU-1", "Caixa", 5, 2],
            ["SKU-2", "Pallet", 0, 0],
        ]
    )

    resultado = analisar("estoque", conteudo, "estoque.xlsx")

    assert resultado.aceitas == 2
    assert resultado.registros[0].quantidade == 5


def test_linha_invalida_nao_aborta_as_demais() -> None:
    conteudo = _csv(
        "sku,nome,quantidade,minimo\n" "SKU-1,Caixa,abc,2\n" "SKU-2,Pallet,3,1\n"
    )

    resultado = analisar("estoque", conteudo, "estoque.csv")

    assert resultado.aceitas == 1
    assert resultado.rejeitadas == 1
    assert resultado.erros[0].linha == 2
    assert "quantidade" in resultado.erros[0].motivo


@pytest.mark.parametrize(
    "texto, motivo_esperado",
    [
        ("sku,nome,quantidade,minimo\n,Caixa,1,1\n", "obrigatório"),
        ("sku,nome,quantidade,minimo\nSKU-1,Caixa,-1,1\n", ">= 0"),
        ("sku,nome,quantidade,minimo\nSKU-1,,1,1\n", "obrigatório"),
    ],
)
def test_estoque_linha_invalida_gera_motivo(texto: str, motivo_esperado: str) -> None:
    resultado = analisar("estoque", _csv(texto), "estoque.csv")

    assert resultado.aceitas == 0
    assert isinstance(resultado.erros[0], ErroLinha)
    assert motivo_esperado in resultado.erros[0].motivo


def test_booleano_invalido_gera_erro() -> None:
    conteudo = _csv("fornecedor_id,nome,ativo\nf-1,TransLog,talvez\n")

    resultado = analisar("fornecedores", conteudo, "fornecedores.csv")

    assert resultado.aceitas == 0
    assert "booleano" in resultado.erros[0].motivo


def test_arquivo_vazio_falha() -> None:
    with pytest.raises(ArquivoVazio):
        analisar("estoque", b"", "estoque.csv")


def test_apenas_cabecalho_nao_gera_erro() -> None:
    resultado = analisar("estoque", _csv("sku,nome,quantidade,minimo\n"), "e.csv")

    assert resultado.aceitas == 0
    assert resultado.rejeitadas == 0


def test_linhas_em_branco_sao_ignoradas() -> None:
    conteudo = _csv("sku,nome,quantidade,minimo\n" "SKU-1,Caixa,1,1\n" "\n" ",,,\n")

    resultado = analisar("estoque", conteudo, "estoque.csv")

    assert resultado.aceitas == 1
    assert resultado.rejeitadas == 0


def test_tipo_desconhecido_falha() -> None:
    with pytest.raises(TipoImportacaoInvalido):
        analisar("financeiro", _csv("col\n1\n"), "x.csv")


def test_colunas_faltando_falha() -> None:
    with pytest.raises(ColunasFaltando) as excinfo:
        analisar("estoque", _csv("sku,nome\nSKU-1,Caixa\n"), "estoque.csv")

    assert "quantidade" in excinfo.value.faltando
    assert "minimo" in excinfo.value.faltando


def test_formato_de_arquivo_invalido_falha() -> None:
    with pytest.raises(FormatoArquivoInvalido):
        analisar("estoque", b"conteudo", "dados.pdf")
