"""Domínio de correções cadastrais com aprovação humana (HITL)."""

from __future__ import annotations

from gestlog.correcoes.completude import (
    CampoCorrecaoInvalido,
    TipoCorrecaoInvalido,
    campos_faltantes,
    valor_atual,
)

__all__ = [
    "CampoCorrecaoInvalido",
    "TipoCorrecaoInvalido",
    "campos_faltantes",
    "valor_atual",
]
