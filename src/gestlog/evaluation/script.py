"""CLI de avaliação: roda o golden set contra o modelo real e salva o relatório.

O modelo real é construído a partir do `.env` (``build_chat_model``); nos testes
injeta-se o fake. Uso: ``uv run python evals/run_golden_set.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel

from gestlog.config import Settings, get_settings
from gestlog.evaluation.golden import carregar_golden_set, run_golden_set
from gestlog.evaluation.relatorio import relatorio_para_dict
from gestlog.llm import build_chat_model

RAIZ = Path(__file__).resolve().parents[3]
GOLDEN_PADRAO = RAIZ / "evals" / "golden_set.json"
RELATORIO_PADRAO = RAIZ / "evals" / "relatorio.json"


def gerar_relatorio(
    caminho_golden: Path = GOLDEN_PADRAO,
    model: BaseChatModel | None = None,
    settings: Settings | None = None,
) -> dict:
    """Executa o golden set e devolve o relatório serializável."""
    resolvido = settings or get_settings()
    modelo = model or build_chat_model(settings=resolvido)
    casos = carregar_golden_set(caminho_golden)
    return relatorio_para_dict(run_golden_set(casos, modelo, resolvido))


def salvar_relatorio(dados: dict, caminho: Path = RELATORIO_PADRAO) -> Path:
    """Grava o relatório em JSON e devolve o caminho gravado."""
    caminho.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return caminho


def main() -> None:  # pragma: no cover
    """Gera, salva e imprime um resumo do relatório de avaliação."""
    dados = gerar_relatorio()
    caminho = salvar_relatorio(dados)
    print(f"Relatório salvo em {caminho}")
    print(f"Acurácia geral: {dados['acuracia']:.0%}")
    for dominio, acuracia in dados["acuracia_por_dominio"].items():
        print(f"  {dominio}: {acuracia:.0%}")
