"""Núcleo testável da avaliação (golden set) do gestlog."""

from __future__ import annotations

from gestlog.evaluation.golden import (
    CasoGolden,
    RelatorioAvaliacao,
    ResultadoCaso,
    carregar_golden_set,
    run_golden_set,
)
from gestlog.evaluation.relatorio import acuracia_por_dominio, relatorio_para_dict

__all__ = [
    "CasoGolden",
    "RelatorioAvaliacao",
    "ResultadoCaso",
    "acuracia_por_dominio",
    "carregar_golden_set",
    "relatorio_para_dict",
    "run_golden_set",
]
