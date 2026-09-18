"""Exceções de importação de dados."""

from __future__ import annotations


class ErroImportacao(Exception):
    """Erro genérico do fluxo de importação."""


class TipoImportacaoInvalido(ErroImportacao):
    """Tipo de dado solicitado não existe no catálogo de importação."""

    def __init__(self, tipo: str) -> None:
        super().__init__(f"Tipo de importação desconhecido: {tipo}")
        self.tipo = tipo


class ArquivoVazio(ErroImportacao):
    """Arquivo sem conteúdo ou sem cabeçalho."""

    def __init__(self) -> None:
        super().__init__("Arquivo vazio ou sem cabeçalho.")


class FormatoArquivoInvalido(ErroImportacao):
    """Arquivo que não é CSV nem planilha suportada."""

    def __init__(self, nome: str) -> None:
        super().__init__(f"Formato de arquivo não suportado: {nome or 'desconhecido'}")
        self.nome = nome


class ColunasFaltando(ErroImportacao):
    """Cabeçalho sem colunas obrigatórias do tipo."""

    def __init__(self, tipo: str, faltando: list[str]) -> None:
        super().__init__(
            f"Colunas obrigatórias ausentes para {tipo}: {', '.join(faltando)}"
        )
        self.tipo = tipo
        self.faltando = faltando
