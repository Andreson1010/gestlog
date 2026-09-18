"""Serialização do relatório do golden set e acurácia por domínio."""

from __future__ import annotations

from gestlog.evaluation.golden import RelatorioAvaliacao


def acuracia_por_dominio(relatorio: RelatorioAvaliacao) -> dict[str, float]:
    """Calcula a acurácia agrupada pelo domínio esperado de cada caso.

    Casos sem domínio esperado (fora de escopo) entram no grupo
    ``fora_de_escopo``.
    """
    grupos: dict[str, list[bool]] = {}
    for resultado in relatorio.resultados:
        chave = resultado.dominio_esperado or "fora_de_escopo"
        grupos.setdefault(chave, []).append(resultado.acertou)
    return {dominio: sum(acertos) / len(acertos) for dominio, acertos in grupos.items()}


def relatorio_para_dict(relatorio: RelatorioAvaliacao) -> dict:
    """Converte o relatório em um dicionário serializável (JSON)."""
    return {
        "total": relatorio.total,
        "acertos": relatorio.acertos,
        "acuracia": relatorio.acuracia,
        "alucinacoes": relatorio.alucinacoes,
        "taxa_alucinacao": relatorio.taxa_alucinacao,
        "fontes_corretas": relatorio.fontes_corretas,
        "taxa_fonte_correta": relatorio.taxa_fonte_correta,
        "acuracia_por_dominio": acuracia_por_dominio(relatorio),
        "resultados": [
            {
                "id": resultado.id,
                "dominio_esperado": resultado.dominio_esperado,
                "dominio_obtido": resultado.dominio_obtido,
                "recomendou": resultado.recomendou,
                "fontes": list(resultado.fontes),
                "acertou": resultado.acertou,
                "alucinou": resultado.alucinou,
                "fonte_correta": resultado.fonte_correta,
            }
            for resultado in relatorio.resultados
        ],
    }
