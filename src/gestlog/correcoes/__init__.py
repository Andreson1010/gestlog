"""Domínio de correções cadastrais com aprovação humana (HITL)."""

from __future__ import annotations

from gestlog.correcoes.completude import (
    CampoCorrecaoInvalido,
    TipoCorrecaoInvalido,
    campos_faltantes,
    natureza,
    serializar,
    valor_atual,
)
from gestlog.correcoes.sugestoes import Sugestao, sugerir

__all__ = [
    "CampoCorrecaoInvalido",
    "Sugestao",
    "TipoCorrecaoInvalido",
    "campos_faltantes",
    "natureza",
    "serializar",
    "sugerir",
    "valor_atual",
]
