"""Testes do módulo de CSV dos relatórios (REL-28..REL-33)."""

from __future__ import annotations

import csv
import io
from datetime import date

import pytest

from gestlog.web.csv_relatorios import gerar_csv, neutralizar, nome_arquivo


def _ler(dados: bytes) -> list[list[str]]:
    texto = dados.decode("utf-8-sig")
    return list(csv.reader(io.StringIO(texto), delimiter=";"))


def test_csv_tem_bom_e_separador_ponto_e_virgula() -> None:
    dados = gerar_csv(["a", "b"], [[1, 2]])

    assert dados.startswith(b"\xef\xbb\xbf")
    texto = dados.decode("utf-8-sig")
    assert "a;b" in texto


def test_csv_apenas_cabecalho() -> None:
    dados = gerar_csv(["SKU", "Nome"], [])

    assert _ler(dados) == [["SKU", "Nome"]]


def test_csv_escapa_campos_especiais_rfc_4180() -> None:
    dados = gerar_csv(
        ["a", "b", "c"],
        [["x;y", 'aspas "aqui"', "linha\nquebrada"]],
    )

    assert _ler(dados)[1] == ["x;y", 'aspas "aqui"', "linha\nquebrada"]


@pytest.mark.parametrize("valor", ["=1+1", "+x", "-x", "@x", "\tx", "\rx"])
def test_neutralizar_prefixa_formula(valor: str) -> None:
    assert neutralizar(valor) == f"'{valor}"


def test_neutralizar_nao_altera_texto_normal() -> None:
    assert neutralizar("ok") == "ok"
    assert neutralizar("") == ""


def test_csv_neutraliza_formula_apenas_em_texto() -> None:
    dados = gerar_csv(["t", "n"], [["=CMD()", -5]])

    assert _ler(dados)[1] == ["'=CMD()", "-5"]


@pytest.mark.parametrize(
    "desde, ate, esperado",
    [
        (None, None, "relatorio-estoque.csv"),
        (date(2026, 9, 1), None, "relatorio-estoque-2026-09-01.csv"),
        (None, date(2026, 9, 30), "relatorio-estoque-2026-09-30.csv"),
        (
            date(2026, 9, 1),
            date(2026, 9, 30),
            "relatorio-estoque-2026-09-01_2026-09-30.csv",
        ),
    ],
)
def test_nome_arquivo_omite_datas_ausentes(
    desde: date | None, ate: date | None, esperado: str
) -> None:
    assert nome_arquivo("estoque", desde, ate) == esperado
