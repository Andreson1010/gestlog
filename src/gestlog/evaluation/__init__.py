"""Núcleo testável da avaliação (golden set) do gestlog."""

from __future__ import annotations

from gestlog.evaluation.golden import (
    CasoGolden,
    RelatorioAvaliacao,
    ResultadoCaso,
    carregar_golden_set,
    run_golden_set,
)

__all__ = [
    "CasoGolden",
    "RelatorioAvaliacao",
    "ResultadoCaso",
    "carregar_golden_set",
    "run_golden_set",
]
