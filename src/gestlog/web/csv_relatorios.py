"""Serialização CSV dos relatórios operacionais (stdlib, sem dependências)."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence
from datetime import date

_SEPARADOR = ";"
_FORMULAS = ("=", "+", "-", "@")
_CONTROLE = ("\t", "\r")


def neutralizar(valor: str) -> str:
    """Neutraliza um texto que planilhas interpretariam como fórmula.

    Prefixa ``'`` quando o valor começa por ``= + - @`` ou por tab/CR. Campos
    numéricos não passam por aqui e permanecem intactos.
    """
    if valor and valor[0] in _FORMULAS + _CONTROLE:
        return f"'{valor}"
    return valor


def gerar_csv(
    cabecalho: Sequence[object],
    linhas: Iterable[Sequence[object]],
) -> bytes:
    """Gera o CSV com separador ``;``, RFC 4180 e codificação UTF-8 com BOM."""
    buffer = io.StringIO()
    escritor = csv.writer(
        buffer,
        delimiter=_SEPARADOR,
        lineterminator="\r\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    escritor.writerow([_celula(valor) for valor in cabecalho])
    for linha in linhas:
        escritor.writerow([_celula(valor) for valor in linha])
    return buffer.getvalue().encode("utf-8-sig")


def nome_arquivo(
    dominio: str,
    desde: date | None = None,
    ate: date | None = None,
) -> str:
    """Monta o nome do arquivo, omitindo datas ausentes."""
    partes = [f"relatorio-{dominio}"]
    if desde is not None:
        partes.append(desde.isoformat())
    nome = "-".join(partes)
    if ate is not None:
        separador = "_" if desde is not None else "-"
        nome = f"{nome}{separador}{ate.isoformat()}"
    return f"{nome}.csv"


def _celula(valor: object) -> object:
    """Aplica a neutralização apenas em campos de texto."""
    if isinstance(valor, str):
        return neutralizar(valor)
    return valor
