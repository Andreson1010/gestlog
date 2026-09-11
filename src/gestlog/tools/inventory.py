"""Ferramentas do especialista em estoque.

Dados mockados e determinísticos: servem de andaime até a integração com o WMS.
"""

from __future__ import annotations

from langchain_core.tools import tool

_ESTOQUE: dict[str, dict[str, object]] = {
    "SKU-100": {
        "nome": "Caixa papelão P",
        "quantidade": 1200,
        "minimo": 500,
        "local": "A1",
    },
    "SKU-200": {
        "nome": "Fita adesiva 48mm",
        "quantidade": 80,
        "minimo": 150,
        "local": "B3",
    },
    "SKU-300": {"nome": "Pallet PBR", "quantidade": 45, "minimo": 20, "local": "C2"},
}

_MOVIMENTACOES: dict[str, str] = {
    "SKU-100": "entrada 800 (há 3 dias); saída 350 (ontem)",
    "SKU-200": "saída 220 (ontem); saída 60 (há 2 dias)",
    "SKU-300": "entrada 30 (há 5 dias); saída 5 (há 1 dia)",
}


@tool
def consultar_estoque(sku: str) -> str:
    """Retorna a quantidade atual, o mínimo e a localização de um SKU."""
    chave = sku.strip().upper()
    dados = _ESTOQUE.get(chave)
    if dados is None:
        return f"SKU {sku} não encontrado no estoque."
    return (
        f"{chave} — {dados['nome']} | quantidade {dados['quantidade']} "
        f"(mínimo {dados['minimo']}) | local {dados['local']}"
    )


@tool
def calcular_reposicao(sku: str, consumo_medio_dia: int) -> str:
    """Sugere quantidade de reposição para um SKU dado o consumo médio diário."""
    chave = sku.strip().upper()
    dados = _ESTOQUE.get(chave)
    if dados is None:
        return f"SKU {sku} não encontrado no estoque."
    if consumo_medio_dia <= 0:
        return "Consumo médio diário deve ser maior que zero."
    quantidade = int(dados["quantidade"])
    dias_restantes = quantidade / consumo_medio_dia
    alvo = max(int(dados["minimo"]) * 2, consumo_medio_dia * 30)
    sugerida = max(0, alvo - quantidade)
    return (
        f"{chave}: {dias_restantes:.1f} dia(s) de cobertura | "
        f"reposição sugerida de {sugerida} unidade(s)"
    )


@tool
def listar_movimentacoes(sku: str) -> str:
    """Lista as movimentações recentes de entrada e saída de um SKU."""
    chave = sku.strip().upper()
    if chave not in _ESTOQUE:
        return f"SKU {sku} não encontrado no estoque."
    return f"{chave}: {_MOVIMENTACOES[chave]}"


TOOLS = [consultar_estoque, calcular_reposicao, listar_movimentacoes]
