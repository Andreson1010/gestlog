"""Redação de PII (e-mails, documentos, nomes, endereços e telefones) antes do LLM.

A redação é determinística e baseada em expressões regulares e em uma lista de
nomes comuns (allowlist), sem chamar o LLM. O texto original é preservado por
quem chama; aqui só se devolve a versão minimizada e as categorias encontradas.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import cache

from gestlog.privacy.politica import (
    CATEGORIA_DOCUMENTO,
    CATEGORIA_EMAIL,
    CATEGORIA_ENDERECO,
    CATEGORIA_NOME,
    CATEGORIA_TELEFONE,
    POLITICA_PADRAO,
    PoliticaRedacao,
)

_PREFIXOS_ENDERECO = (
    r"Rua|Avenida|Alameda|Travessa|Rodovia|Estrada|Praça|R\.|Av\.|Al\.|Rod\."
)
_PALAVRA_ENDERECO = r"[A-Za-zÀ-ÿ0-9º°]+"
_ENDERECO: re.Pattern[str] = re.compile(
    rf"\b(?:{_PREFIXOS_ENDERECO})\s+{_PALAVRA_ENDERECO}"
    rf"(?:\s+{_PALAVRA_ENDERECO}){{0,3}}?"
    r"\s*,?\s*(?:n[ºo°]?\.?\s*)?\d+[A-Za-z]?\b",
    re.IGNORECASE,
)
_CEP: re.Pattern[str] = re.compile(r"\b\d{5}-\d{3}\b")
_TELEFONE: re.Pattern[str] = re.compile(
    r"(?:(?:\+|00)\s?55\s?)?(?:\(?\d{2}\)?[\s.-]?)(?:9\d{4}|\d{4})[\s.-]?\d{4}\b"
)
_EMAIL: re.Pattern[str] = re.compile(r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_CNPJ: re.Pattern[str] = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_CPF: re.Pattern[str] = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")


@dataclass(frozen=True)
class RedactedText:
    """Texto redigido e as categorias de PII que foram encontradas."""

    texto: str
    categorias: tuple[str, ...] = ()

    @property
    def houve_redacao(self) -> bool:
        """Indica se ao menos uma ocorrência de PII foi redigida."""
        return bool(self.categorias)


def _sem_acento(texto: str) -> str:
    """Devolve ``texto`` sem diacríticos, para casar nomes digitados sem acento."""
    decomposto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in decomposto if not unicodedata.combining(c))


@cache
def _padrao_nomes(nomes: frozenset[str]) -> re.Pattern[str]:
    """Compila (e memoiza) o padrão que casa nomes conhecidos e sobrenomes."""
    formas = {forma for nome in nomes for forma in (nome, _sem_acento(nome))}
    alternancia = "|".join(
        re.escape(nome) for nome in sorted(formas, key=lambda nome: (-len(nome), nome))
    )
    return re.compile(
        rf"\b(?:{alternancia})\b"
        r"(?:(?:\s+(?i:de|da|do|dos|das))?\s+(?-i:[A-ZÀ-Ý][a-zà-ÿ]+))*",
        re.IGNORECASE,
    )


def _regras(politica: PoliticaRedacao) -> tuple[tuple[str, re.Pattern[str], str], ...]:
    """Monta a sequência de redação com categoria, padrão e marcador.

    A ordem é fixa: e-mail primeiro (o ``@`` o torna disjunto das demais);
    documento antes de telefone (os dois compartilham dígitos pontuados — um
    CPF mascarado vira ``[DOCUMENTO]``, nunca ``[TELEFONE]``); CNPJ antes de
    CPF remove a ambiguidade entre as máscaras; o restante segue como antes.
    """
    return (
        (CATEGORIA_EMAIL, _EMAIL, politica.marcador_email),
        (CATEGORIA_DOCUMENTO, _CNPJ, politica.marcador_documento),
        (CATEGORIA_DOCUMENTO, _CPF, politica.marcador_documento),
        (CATEGORIA_TELEFONE, _TELEFONE, politica.marcador_telefone),
        (CATEGORIA_ENDERECO, _ENDERECO, politica.marcador_endereco),
        (CATEGORIA_ENDERECO, _CEP, politica.marcador_endereco),
        (CATEGORIA_NOME, _padrao_nomes(politica.nomes), politica.marcador_nome),
    )


def redact(
    texto: str,
    politica: PoliticaRedacao = POLITICA_PADRAO,
) -> RedactedText:
    """Devolve ``texto`` sem e-mails, documentos, nomes, endereços e telefones.

    Texto sem PII passa intacto (``categorias`` vazio). A substituição é feita
    por marcadores como ``[EMAIL]``, ``[DOCUMENTO]``, ``[NOME]``, ``[ENDERECO]``
    e ``[TELEFONE]``.
    """
    resultado = texto
    categorias: list[str] = []
    for categoria, padrao, marcador in _regras(politica):
        resultado, quantidade = padrao.subn(marcador.replace("\\", r"\\"), resultado)
        if quantidade and categoria not in categorias:
            categorias.append(categoria)
    return RedactedText(texto=resultado, categorias=tuple(categorias))
