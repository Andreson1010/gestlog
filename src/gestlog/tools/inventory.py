"""Ferramentas do especialista em estoque.

As tools de leitura consultam o repositório do tenant (``StockRepository``),
filtrando sempre pelo ``empresa_id`` para individualizar os dados entre clientes
do SaaS. ``build_inventory_tools`` prende o repositório e a empresa no closure,
preservando as assinaturas das tools (``sku``, ``consumo_medio_dia`` etc.).

``TOOLS`` (mock determinístico) permanece como andaime usado pelo grafo e pelo
REPL; o Copilot Service injeta a fábrica quando estiver disponível (T19).
"""

from __future__ import annotations

from uuid import UUID

from langchain_core.tools import BaseTool, tool

from gestlog.repositories.catalog import StockRepository

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

_DIAS_COBERTURA = 30
_FATOR_EXCEDENTE = 2


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


def build_inventory_tools(repo: StockRepository, empresa_id: UUID) -> list[BaseTool]:
    """Constrói as tools de estoque amarradas ao repositório do tenant.

    As tools de leitura e análise consultam ``repo`` filtrando por
    ``empresa_id``, preservando as assinaturas chamadas pelo LLM.
    """

    @tool
    def consultar_estoque(sku: str) -> str:
        """Retorna a quantidade atual, o mínimo e a localização de um SKU."""
        chave = sku.strip().upper()
        item = repo.get_by_sku(empresa_id, chave)
        if item is None:
            return f"SKU {sku} não encontrado no estoque."
        return (
            f"{chave} — {item.nome} | quantidade {item.quantidade} "
            f"(mínimo {item.minimo}) | local {item.local}"
        )

    @tool
    def calcular_reposicao(sku: str, consumo_medio_dia: int) -> str:
        """Sugere quantidade de reposição para um SKU dado o consumo médio diário."""
        chave = sku.strip().upper()
        item = repo.get_by_sku(empresa_id, chave)
        if item is None:
            return f"SKU {sku} não encontrado no estoque."
        if consumo_medio_dia <= 0:
            return "Consumo médio diário deve ser maior que zero."
        dias_restantes = item.quantidade / consumo_medio_dia
        alvo = max(item.minimo * _FATOR_EXCEDENTE, consumo_medio_dia * _DIAS_COBERTURA)
        sugerida = max(0, alvo - item.quantidade)
        return (
            f"{chave}: {dias_restantes:.1f} dia(s) de cobertura | "
            f"reposição sugerida de {sugerida} unidade(s)"
        )

    @tool
    def listar_movimentacoes(sku: str) -> str:
        """Informa as movimentações registradas de um SKU no repositório."""
        chave = sku.strip().upper()
        item = repo.get_by_sku(empresa_id, chave)
        if item is None:
            return f"SKU {sku} não encontrado no estoque."
        return f"{chave}: sem movimentações registradas no repositório"

    @tool
    def prever_demanda(sku: str, consumo_medio_dia: int) -> str:
        """Projeta a demanda de um SKU para o período de cobertura padrão."""
        chave = sku.strip().upper()
        item = repo.get_by_sku(empresa_id, chave)
        if item is None:
            return f"SKU {sku} não encontrado no estoque."
        if consumo_medio_dia <= 0:
            return "Consumo médio diário deve ser maior que zero."
        projetada = consumo_medio_dia * _DIAS_COBERTURA
        return (
            f"{chave}: demanda projetada de {projetada} unidade(s) "
            f"em {_DIAS_COBERTURA} dia(s)"
        )

    @tool
    def otimizar_armazem() -> str:
        """Aponta SKUs abaixo do mínimo e sugere reorganização por localização."""
        itens = repo.list(empresa_id)
        abaixo = [item for item in itens if item.quantidade < item.minimo]
        if not abaixo:
            return "Nenhum SKU abaixo do mínimo; armazém dentro do esperado."
        linhas = [
            f"{item.sku}: {item.quantidade}/{item.minimo} (local {item.local})"
            for item in abaixo
        ]
        return "SKUs abaixo do mínimo:\n" + "\n".join(linhas)

    @tool
    def otimizar_custos() -> str:
        """Analisa custo de manutenção: SKUs com estoque acima do dobro do mínimo."""
        itens = repo.list(empresa_id)
        excedentes = [
            item for item in itens if item.quantidade > item.minimo * _FATOR_EXCEDENTE
        ]
        if not excedentes:
            return "Nenhum SKU com estoque excedente identificado."
        linhas = [
            f"{item.sku}: {item.quantidade} un. (mínimo {item.minimo})"
            for item in excedentes
        ]
        return "SKUs com estoque excedente (custo de manutenção):\n" + "\n".join(linhas)

    return [
        consultar_estoque,
        calcular_reposicao,
        listar_movimentacoes,
        prever_demanda,
        otimizar_armazem,
        otimizar_custos,
    ]
