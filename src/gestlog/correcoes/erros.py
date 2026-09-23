"""Exceções de domínio do fluxo de correções com aprovação humana."""

from __future__ import annotations


class ErroCorrecao(Exception):
    """Erro base do domínio de correções cadastrais."""


class CorrecaoNaoEncontrada(ErroCorrecao):
    """Item inexistente no escopo da empresa da sessão (HTTP 404)."""

    def __init__(self) -> None:
        super().__init__("Item de correção não encontrado.")


class CorrecaoNaoAprovavel(ErroCorrecao):
    """Item em estado que não permite aprovação (HTTP 409), sem alterá-lo."""

    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


class CorrecaoAlvoInvalido(ErroCorrecao):
    """Alvo ausente ou alterado; item encerrado como falha (HTTP 409)."""

    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


class CorrecaoFalhaEscrita(ErroCorrecao):
    """Exceção durante a escrita; item encerrado como falha, sem escrita parcial."""

    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo
