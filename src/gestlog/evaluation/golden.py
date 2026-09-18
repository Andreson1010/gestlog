"""Formato e runner do golden set de avaliação por domínio (QUA-01).

O golden set é uma lista de casos com a pergunta, o domínio esperado e as fontes
que deveriam embasar a recomendação. O runner executa cada caso no grafo (com um
modelo injetado — fake nos testes, real no script da T30) e agrega acurácia,
alucinação e acerto de fonte em um relatório.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel

from gestlog.config import Settings, get_settings
from gestlog.copilot.service import extrair_recomendacao, texto_resposta
from gestlog.graph import build_graph, run_query


@dataclass(frozen=True)
class CasoGolden:
    """Um caso do golden set: pergunta, domínio e fontes esperadas."""

    id: str
    pergunta: str
    dominio: str
    fontes_esperadas: tuple[str, ...] = ()
    requer_recomendacao: bool = True


@dataclass(frozen=True)
class ResultadoCaso:
    """Resultado avaliado de um caso do golden set."""

    id: str
    dominio_esperado: str
    dominio_obtido: str
    recomendou: bool
    fontes: tuple[str, ...]
    acertou: bool
    alucinou: bool
    fonte_correta: bool


@dataclass(frozen=True)
class RelatorioAvaliacao:
    """Agrega os resultados do golden set com as taxas de qualidade."""

    resultados: tuple[ResultadoCaso, ...] = ()

    @property
    def total(self) -> int:
        """Quantidade de casos avaliados."""
        return len(self.resultados)

    @property
    def acertos(self) -> int:
        """Quantidade de casos com recomendação/insuficiência esperada."""
        return sum(resultado.acertou for resultado in self.resultados)

    @property
    def alucinacoes(self) -> int:
        """Quantidade de casos em que se recomendou sem base esperada."""
        return sum(resultado.alucinou for resultado in self.resultados)

    @property
    def fontes_corretas(self) -> int:
        """Quantidade de casos com as fontes esperadas presentes."""
        return sum(resultado.fonte_correta for resultado in self.resultados)

    @property
    def acuracia(self) -> float:
        """Fração de casos corretos (0.0 quando não há casos)."""
        return self.acertos / self.total if self.total else 0.0

    @property
    def taxa_alucinacao(self) -> float:
        """Fração de casos com alucinação (0.0 quando não há casos)."""
        return self.alucinacoes / self.total if self.total else 0.0

    @property
    def taxa_fonte_correta(self) -> float:
        """Fração de casos com fonte correta (0.0 quando não há casos)."""
        return self.fontes_corretas / self.total if self.total else 0.0


def carregar_golden_set(caminho: Path) -> tuple[CasoGolden, ...]:
    """Lê e valida um arquivo JSON de golden set, devolvendo os casos."""
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if not isinstance(dados, list):
        raise ValueError("Golden set deve ser uma lista de casos.")
    return tuple(_caso_de_dict(item) for item in dados)


def _caso_de_dict(item: object) -> CasoGolden:
    """Converte um item JSON em ``CasoGolden``, rejeitando formato inválido."""
    if not isinstance(item, dict):
        raise ValueError(f"Caso de golden set inválido: {item!r}")
    try:
        fontes = item.get("fontes_esperadas", [])
        requerido = item.get("requer_recomendacao", True)
        if not isinstance(fontes, list) or not all(
            isinstance(fonte, str) for fonte in fontes
        ):
            raise TypeError("fontes_esperadas deve ser uma lista de strings")
        if not isinstance(requerido, bool):
            raise TypeError("requer_recomendacao deve ser booleano")
        return CasoGolden(
            id=str(item["id"]),
            pergunta=str(item["pergunta"]),
            dominio=str(item["dominio"]),
            fontes_esperadas=tuple(fontes),
            requer_recomendacao=requerido,
        )
    except (KeyError, TypeError) as erro:
        raise ValueError(f"Caso de golden set inválido: {item!r}") from erro


def _avaliar_caso(caso: CasoGolden, bruto: str, dominio_obtido: str) -> ResultadoCaso:
    """Compara a recomendação obtida com o que o caso esperava."""
    recomendacao = extrair_recomendacao(bruto, dominio_obtido)
    recomendou = not recomendacao.insuficiente
    if caso.requer_recomendacao:
        acertou = recomendou and dominio_obtido == caso.dominio
        fonte_correta = all(
            fonte in recomendacao.fontes for fonte in caso.fontes_esperadas
        )
    else:
        acertou = not recomendou
        fonte_correta = not recomendou
    return ResultadoCaso(
        id=caso.id,
        dominio_esperado=caso.dominio,
        dominio_obtido=dominio_obtido,
        recomendou=recomendou,
        fontes=recomendacao.fontes,
        acertou=acertou,
        alucinou=recomendou and not caso.requer_recomendacao,
        fonte_correta=fonte_correta,
    )


def run_golden_set(
    casos: tuple[CasoGolden, ...],
    model: BaseChatModel,
    settings: Settings | None = None,
) -> RelatorioAvaliacao:
    """Executa o golden set no grafo e devolve o relatório agregado."""
    resolvido = settings or get_settings()
    grafo = build_graph(model=model, settings=resolvido)
    resultados = []
    for caso in casos:
        estado = run_query(
            grafo, caso.pergunta, recursion_limit=resolvido.recursion_limit
        )
        resultados.append(
            _avaliar_caso(
                caso,
                texto_resposta(estado["messages"]),
                str(estado.get("dominio", "")),
            )
        )
    return RelatorioAvaliacao(resultados=tuple(resultados))
