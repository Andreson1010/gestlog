"""Redação de PII antes do envio de texto ao LLM."""

from __future__ import annotations

from gestlog.privacy.politica import (
    CATEGORIA_DOCUMENTO,
    CATEGORIA_EMAIL,
    CATEGORIA_ENDERECO,
    CATEGORIA_NOME,
    CATEGORIA_TELEFONE,
    POLITICA_PADRAO,
    PoliticaRedacao,
)
from gestlog.privacy.redacao import RedactedText, redact

__all__ = [
    "CATEGORIA_DOCUMENTO",
    "CATEGORIA_EMAIL",
    "CATEGORIA_ENDERECO",
    "CATEGORIA_NOME",
    "CATEGORIA_TELEFONE",
    "POLITICA_PADRAO",
    "PoliticaRedacao",
    "RedactedText",
    "redact",
]
