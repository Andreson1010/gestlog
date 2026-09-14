"""Importação de dados por tipo (CSV/planilha) com validação por linha."""

from __future__ import annotations

from gestlog.ingestion.erros import (
    ArquivoVazio,
    ColunasFaltando,
    ErroImportacao,
    FormatoArquivoInvalido,
    TipoImportacaoInvalido,
)
from gestlog.ingestion.modelos import (
    ErroLinha,
    RegistroEstoque,
    RegistroFornecedor,
    RegistroTransporte,
    ResultadoImportacao,
)
from gestlog.ingestion.parser import COLUNAS_OBRIGATORIAS, analisar
from gestlog.ingestion.servico import historico, importar

__all__ = [
    "COLUNAS_OBRIGATORIAS",
    "ArquivoVazio",
    "ColunasFaltando",
    "ErroImportacao",
    "ErroLinha",
    "FormatoArquivoInvalido",
    "RegistroEstoque",
    "RegistroFornecedor",
    "RegistroTransporte",
    "ResultadoImportacao",
    "TipoImportacaoInvalido",
    "analisar",
    "historico",
    "importar",
]
