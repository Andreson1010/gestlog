"""Testes do formato e do runner do golden set (sem rede)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from gestlog.config import Settings
from gestlog.evaluation import (
    CasoGolden,
    RelatorioAvaliacao,
    carregar_golden_set,
    run_golden_set,
)

_CAMINHO_GOLDEN = Path(__file__).resolve().parents[2] / "evals" / "golden_set.json"


def _tool_comum(resposta: str, fontes: str = "") -> list[dict[str, Any]]:
    return [
        {
            "name": "enviar_resposta_logistica",
            "args": {"resposta": resposta, "fontes": fontes},
            "id": "call-1",
            "type": "tool_call",
        }
    ]


def _modelo_para(casos: tuple[CasoGolden, ...], fake_model_cls: type) -> Any:
    routes: list[str] = []
    tool_calls: list[list[dict[str, Any]]] = []
    for caso in casos:
        if caso.requer_recomendacao:
            routes.append(caso.dominio)
            tool_calls.append(
                _tool_comum("resposta", fontes=",".join(caso.fontes_esperadas))
            )
        routes.append("FINISH")
    return fake_model_cls(routes=routes, tool_calls=tool_calls, final="sem base")


def test_run_golden_set_reporta_acuracia_total(fake_model_cls: type) -> None:
    casos = (
        CasoGolden("e1", "tem estoque?", "estoque", ("estoque",)),
        CasoGolden("f1", "qual fornecedor?", "fornecedores", ("fornecedores",)),
        CasoGolden("t1", "status do rastreio?", "transporte", ("TMS",)),
    )

    relatorio = run_golden_set(
        casos, _modelo_para(casos, fake_model_cls), Settings(_env_file=None)
    )

    assert relatorio.total == 3
    assert relatorio.acertos == 3
    assert relatorio.acuracia == 1.0
    assert relatorio.alucinacoes == 0
    assert relatorio.fontes_corretas == 3


def test_run_golden_set_detecta_fonte_errada(fake_model_cls: type) -> None:
    casos = (CasoGolden("e1", "tem estoque?", "estoque", ("estoque",)),)
    model = fake_model_cls(
        routes=["estoque", "FINISH"],
        tool_calls=[_tool_comum("resposta", fontes="outra")],
    )

    relatorio = run_golden_set(casos, model, Settings(_env_file=None))

    assert relatorio.acertos == 1
    assert relatorio.fontes_corretas == 0
    assert relatorio.taxa_fonte_correta == 0.0


def test_run_golden_set_detecta_alucinacao(fake_model_cls: type) -> None:
    caso = CasoGolden("x", "qual a capital?", "", requer_recomendacao=False)
    model = fake_model_cls(
        routes=["estoque", "FINISH"],
        tool_calls=[_tool_comum("Paris", fontes="vies")],
    )

    relatorio = run_golden_set((caso,), model, Settings(_env_file=None))

    resultado = relatorio.resultados[0]
    assert resultado.recomendou is True
    assert resultado.alucinou is True
    assert resultado.acertou is False
    assert relatorio.alucinacoes == 1
    assert relatorio.taxa_alucinacao == 1.0


def test_relatorio_vazio_zera_taxas() -> None:
    relatorio = RelatorioAvaliacao()

    assert relatorio.total == 0
    assert relatorio.acuracia == 0.0
    assert relatorio.taxa_alucinacao == 0.0
    assert relatorio.taxa_fonte_correta == 0.0


def test_carregar_golden_set_do_arquivo() -> None:
    casos = carregar_golden_set(_CAMINHO_GOLDEN)

    assert [caso.id for caso in casos] == ["est-01", "for-01", "tra-01"]
    assert casos[0].dominio == "estoque"
    assert casos[2].fontes_esperadas == ("TMS",)


def test_run_golden_set_com_arquivo(fake_model_cls: type) -> None:
    casos = carregar_golden_set(_CAMINHO_GOLDEN)

    relatorio = run_golden_set(
        casos, _modelo_para(casos, fake_model_cls), Settings(_env_file=None)
    )

    assert relatorio.acuracia == 1.0


def test_carregar_golden_set_rejeita_nao_lista(tmp_path: Path) -> None:
    caminho = tmp_path / "golden.json"
    caminho.write_text('{"id": "x"}', encoding="utf-8")

    with pytest.raises(ValueError):
        carregar_golden_set(caminho)


def test_carregar_golden_set_rejeita_caso_incompleto(tmp_path: Path) -> None:
    caminho = tmp_path / "golden.json"
    caminho.write_text('[{"id": "x"}]', encoding="utf-8")

    with pytest.raises(ValueError):
        carregar_golden_set(caminho)


def test_carregar_golden_set_rejeita_item_nao_objeto(tmp_path: Path) -> None:
    caminho = tmp_path / "golden.json"
    caminho.write_text('["x"]', encoding="utf-8")

    with pytest.raises(ValueError):
        carregar_golden_set(caminho)


def test_carregar_golden_set_rejeita_tipos_invalidos(tmp_path: Path) -> None:
    caminho = tmp_path / "golden.json"
    caminho.write_text(
        '[{"id": "x", "pergunta": "p", "dominio": "estoque", '
        '"fontes_esperadas": "estoque"}]',
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        carregar_golden_set(caminho)


def test_carregar_golden_set_rejeita_requer_nao_booleano(tmp_path: Path) -> None:
    caminho = tmp_path / "golden.json"
    caminho.write_text(
        '[{"id": "x", "pergunta": "p", "dominio": "estoque", '
        '"requer_recomendacao": "sim"}]',
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        carregar_golden_set(caminho)
