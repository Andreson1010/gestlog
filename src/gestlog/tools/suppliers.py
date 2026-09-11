"""Ferramentas do especialista em fornecedores.

Dados mockados e determinísticos: servem de andaime até a integração com o ERP.
"""

from __future__ import annotations

from langchain_core.tools import tool

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
