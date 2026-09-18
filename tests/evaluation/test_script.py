"""Testes do script de avaliação (golden set) sem tocar a rede."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gestlog.config import Settings
from gestlog.evaluation import (
    CasoGolden,
    RelatorioAvaliacao,
    ResultadoCaso,
    acuracia_por_dominio,
    carregar_golden_set,
    relatorio_para_dict,
)
from gestlog.evaluation.script import GOLDEN_PADRAO, gerar_relatorio, salvar_relatorio

_MOCK_FONTES = {
    "estoque": "estoque",
    "fornecedores": "fornecedores",
    "transporte": "TMS",
}


def _tool_comum(resposta: str, fontes: str) -> list[dict[str, Any]]:
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
            fontes = _MOCK_FONTES.get(caso.dominio, ",".join(caso.fontes_esperadas))
            tool_calls.append(_tool_comum("resposta", fontes))
        routes.append("FINISH")
    return fake_model_cls(routes=routes, tool_calls=tool_calls, final="sem base")


def _escrever_golden(caminho: Path, casos: tuple[CasoGolden, ...]) -> None:
    dados = [
        {
            "id": caso.id,
            "pergunta": caso.pergunta,
            "dominio": caso.dominio,
            "fontes_esperadas": list(caso.fontes_esperadas),
        }
        for caso in casos
    ]
    caminho.write_text(json.dumps(dados), encoding="utf-8")


def test_gerar_relatorio_traz_acuracia_por_dominio(
    tmp_path: Path, fake_model_cls: type
) -> None:
    caminho = tmp_path / "golden.json"
    _escrever_golden(
        caminho,
        (
            CasoGolden("e1", "tem estoque?", "estoque", ("estoque",)),
            CasoGolden("t1", "status do rastreio?", "transporte", ("TMS",)),
        ),
    )
    casos = carregar_golden_set(caminho)
    model = _modelo_para(casos, fake_model_cls)

    dados = gerar_relatorio(caminho, model, Settings(_env_file=None))

    assert dados["total"] == 2
    assert dados["acuracia"] == 1.0
    assert dados["acuracia_por_dominio"] == {"estoque": 1.0, "transporte": 1.0}
    assert json.dumps(dados)  # serializável


def test_gerar_relatorio_com_golden_padrao(fake_model_cls: type) -> None:
    casos = carregar_golden_set(GOLDEN_PADRAO)
    model = _modelo_para(casos, fake_model_cls)

    dados = gerar_relatorio(GOLDEN_PADRAO, model, Settings(_env_file=None))

    assert set(dados["acuracia_por_dominio"]) == {
        "estoque",
        "fornecedores",
        "transporte",
    }
    assert dados["acuracia"] == 1.0


def test_salvar_relatorio_escreve_json(tmp_path: Path) -> None:
    destino = tmp_path / "relatorio.json"
    dados = {"acuracia": 1.0, "acuracia_por_dominio": {"estoque": 1.0}}

    caminho = salvar_relatorio(dados, destino)

    assert caminho == destino
    assert json.loads(destino.read_text(encoding="utf-8")) == dados


def test_acuracia_por_dominio_agrupa_fora_de_escopo() -> None:
    relatorio = RelatorioAvaliacao(
        resultados=(
            ResultadoCaso(
                "a", "estoque", "estoque", True, ("estoque",), True, False, True
            ),
            ResultadoCaso("b", "", "", False, (), True, False, True),
        )
    )

    assert acuracia_por_dominio(relatorio) == {
        "estoque": 1.0,
        "fora_de_escopo": 1.0,
    }
    assert "acuracia_por_dominio" in relatorio_para_dict(relatorio)
