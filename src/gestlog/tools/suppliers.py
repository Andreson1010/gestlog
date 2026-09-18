"""Ferramentas do especialista em fornecedores.

As tools de leitura consultam o repositório do tenant (``SupplierRepository``),
filtrando sempre pelo ``empresa_id`` para individualizar os dados entre clientes
do SaaS. ``build_supplier_tools`` prende o repositório e a empresa no closure,
preservando as assinaturas das tools (``categoria``, ``fornecedor_id``).

``TOOLS`` (mock determinístico) permanece como fallback do REPL (``cli.py``);
o Copilot Service injeta esta fábrica por requisição (T17).
"""

from __future__ import annotations

from uuid import UUID

from langchain_core.tools import BaseTool, tool

from gestlog.db.models import Supplier
from gestlog.repositories.catalog import SupplierRepository

_FORNECEDORES: dict[str, dict[str, object]] = {
    "F-001": {
        "nome": "TransLog Cargas",
        "categoria": "transporte",
        "prazo_dias": 5,
        "avaliacao": 4.6,
        "ativo": True,
    },
    "F-002": {
        "nome": "Insumos Silva",
        "categoria": "insumos",
        "prazo_dias": 12,
        "avaliacao": 3.2,
        "ativo": True,
    },
    "F-003": {
        "nome": "Embalagens Norte",
        "categoria": "embalagens",
        "prazo_dias": 8,
        "avaliacao": 4.1,
        "ativo": False,
    },
}

_OCORRENCIAS: dict[str, str] = {
    "F-001": "2 atrasos em 40 pedidos (95% no prazo)",
    "F-002": "7 atrasos em 30 pedidos (77% no prazo)",
    "F-003": "fornecedor inativo desde o último trimestre",
}

_AVALIACAO_MINIMA = 4.0
_PRAZO_MAXIMO_DIAS = 15


@tool
def listar_fornecedores(categoria: str) -> str:
    """Lista fornecedores ativos de uma categoria (ex.: transporte, insumos)."""
    alvo = categoria.strip().lower()
    encontrados = [
        f"{fid} — {dados['nome']} (nota {dados['avaliacao']})"
        for fid, dados in _FORNECEDORES.items()
        if dados["ativo"] and str(dados["categoria"]).lower() == alvo
    ]
    if not encontrados:
        return f"Nenhum fornecedor ativo na categoria '{categoria}'."
    return "\n".join(encontrados)


@tool
def consultar_fornecedor(fornecedor_id: str) -> str:
    """Retorna os dados cadastrais de um fornecedor pelo seu identificador."""
    chave = fornecedor_id.strip().upper()
    dados = _FORNECEDORES.get(chave)
    if dados is None:
        return f"Fornecedor {fornecedor_id} não encontrado."
    status = "ativo" if dados["ativo"] else "inativo"
    return (
        f"{chave} — {dados['nome']} | categoria {dados['categoria']} | "
        f"prazo médio {dados['prazo_dias']} dias | nota {dados['avaliacao']} | {status}"
    )


@tool
def avaliar_desempenho(fornecedor_id: str) -> str:
    """Resume o histórico de desempenho e atrasos de um fornecedor."""
    chave = fornecedor_id.strip().upper()
    if chave not in _FORNECEDORES:
        return f"Fornecedor {fornecedor_id} não encontrado."
    return f"{chave}: {_OCORRENCIAS[chave]}"


TOOLS = [listar_fornecedores, consultar_fornecedor, avaliar_desempenho]


def _motivos_conformidade(fornecedor: Supplier) -> list[str]:
    """Lista os motivos de não conformidade de um fornecedor do tenant."""
    motivos: list[str] = []
    if not fornecedor.ativo:
        motivos.append("inativo")
    if fornecedor.avaliacao < _AVALIACAO_MINIMA:
        motivos.append(f"nota {fornecedor.avaliacao} abaixo de {_AVALIACAO_MINIMA}")
    if fornecedor.prazo_dias > _PRAZO_MAXIMO_DIAS:
        motivos.append(
            f"prazo {fornecedor.prazo_dias} dias acima de {_PRAZO_MAXIMO_DIAS}"
        )
    return motivos


def build_supplier_tools(repo: SupplierRepository, empresa_id: UUID) -> list[BaseTool]:
    """Constrói as tools de fornecedores amarradas ao repositório do tenant.

    As tools de leitura e análise consultam ``repo`` filtrando por
    ``empresa_id``, preservando as assinaturas chamadas pelo LLM.
    """

    @tool
    def listar_fornecedores(categoria: str) -> str:
        """Lista fornecedores ativos de uma categoria (ex.: transporte, insumos)."""
        alvo = categoria.strip().lower()
        encontrados = [
            f"{item.fornecedor_id} — {item.nome} (nota {item.avaliacao})"
            for item in repo.list(empresa_id)
            if item.ativo and item.categoria.lower() == alvo
        ]
        if not encontrados:
            return f"Nenhum fornecedor ativo na categoria '{categoria}'."
        return "\n".join(encontrados)

    @tool
    def consultar_fornecedor(fornecedor_id: str) -> str:
        """Retorna os dados cadastrais de um fornecedor pelo seu identificador."""
        chave = fornecedor_id.strip().upper()
        item = repo.get_by_fornecedor_id(empresa_id, chave)
        if item is None:
            return f"Fornecedor {fornecedor_id} não encontrado."
        status = "ativo" if item.ativo else "inativo"
        return (
            f"{item.fornecedor_id} — {item.nome} | categoria {item.categoria} | "
            f"prazo médio {item.prazo_dias} dias | nota {item.avaliacao} | {status}"
        )

    @tool
    def avaliar_desempenho(fornecedor_id: str) -> str:
        """Resume o desempenho cadastrado de um fornecedor do tenant."""
        chave = fornecedor_id.strip().upper()
        item = repo.get_by_fornecedor_id(empresa_id, chave)
        if item is None:
            return f"Fornecedor {fornecedor_id} não encontrado."
        status = "ativo" if item.ativo else "inativo"
        return (
            f"{item.fornecedor_id}: nota {item.avaliacao} | "
            f"prazo médio {item.prazo_dias} dia(s) | {status}"
        )

    @tool
    def tratar_conformidade() -> str:
        """Checa fornecedores em não conformidade do tenant."""
        fornecedores = repo.list(empresa_id)
        if not fornecedores:
            return "Nenhum fornecedor cadastrado para análise de conformidade."
        pendentes: list[str] = []
        for item in fornecedores:
            motivos = _motivos_conformidade(item)
            if motivos:
                pendentes.append(f"{item.fornecedor_id}: " + ", ".join(motivos))
        if not pendentes:
            return "Todos os fornecedores em conformidade."
        return "Fornecedores em não conformidade:\n" + "\n".join(pendentes)

    return [
        listar_fornecedores,
        consultar_fornecedor,
        avaliar_desempenho,
        tratar_conformidade,
    ]
