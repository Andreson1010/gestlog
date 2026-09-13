"""Estruturas de dados do resultado de importação."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ErroLinha:
    """Erro de validação de uma linha, com o número da linha e o motivo."""

    linha: int
    motivo: str


@dataclass(frozen=True)
class RegistroEstoque:
    """Linha normalizada de estoque."""

    sku: str
    nome: str
    quantidade: int
    minimo: int
    local: str = ""


@dataclass(frozen=True)
class RegistroFornecedor:
    """Linha normalizada de fornecedor."""

    fornecedor_id: str
    nome: str
    categoria: str = ""
    prazo_dias: int = 0
    avaliacao: float = 0.0
    ativo: bool = True


@dataclass(frozen=True)
class RegistroTransporte:
    """Linha normalizada de transporte."""

    codigo_rastreio: str
    origem: str
    destino: str
    peso_kg: float
    status: str = ""


Registro = RegistroEstoque | RegistroFornecedor | RegistroTransporte


@dataclass(frozen=True)
class ResultadoImportacao:
    """Registros aceitos e erros por linha de uma importação."""

    tipo: str
    registros: tuple[Registro, ...]
    erros: tuple[ErroLinha, ...]

    @property
    def aceitas(self) -> int:
        """Total de linhas aceitas."""
        return len(self.registros)

    @property
    def rejeitadas(self) -> int:
        """Total de linhas rejeitadas."""
        return len(self.erros)
