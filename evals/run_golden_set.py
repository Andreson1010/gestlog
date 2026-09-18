"""Launcher do script de avaliação do golden set (T30).

A lógica testável vive em ``gestlog.evaluation.script``; aqui só se dispara a CLI.
Uso: ``uv run python evals/run_golden_set.py``.
"""

from __future__ import annotations

from gestlog.evaluation.script import main

if __name__ == "__main__":
    main()
