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
from gestlog.correcoes.erros import (
    CorrecaoAlvoInvalido,
    CorrecaoFalhaEscrita,
    CorrecaoNaoAprovavel,
    CorrecaoNaoEncontrada,
    ErroCorrecao,
    JustificativaObrigatoria,
)
from gestlog.correcoes.servico import CorrectionService
from gestlog.correcoes.sugestoes import Sugestao, sugerir

__all__ = [
    "CampoCorrecaoInvalido",
    "CorrecaoAlvoInvalido",
    "CorrecaoFalhaEscrita",
    "CorrecaoNaoAprovavel",
    "CorrecaoNaoEncontrada",
    "CorrectionService",
    "ErroCorrecao",
    "JustificativaObrigatoria",
    "Sugestao",
    "TipoCorrecaoInvalido",
    "campos_faltantes",
    "natureza",
    "serializar",
    "sugerir",
    "valor_atual",
]
