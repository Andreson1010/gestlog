"""Ferramentas do especialista em transporte.

``rastrear_entrega`` e ``otimizar_entrega`` consultam o repositório do tenant
(``TransportRepository``), filtrando sempre pelo ``empresa_id`` para
individualizar os dados entre clientes do SaaS. ``calcular_frete`` e
``consultar_prazo`` preservam o cálculo determinístico (tabela de distâncias +
tarifas) e são reaproveitados tanto pelo mock quanto pela fábrica.

``build_transport_tools`` prende o repositório e a empresa no closure,
preservando as assinaturas das tools. ``TOOLS`` (mock determinístico) permanece
como andaime usado pelo grafo e pelo REPL; o Copilot Service injeta a fábrica
quando estiver disponível (T19).
"""

from __future__ import annotations

import math
from uuid import UUID

from langchain_core.tools import BaseTool, tool

from gestlog.repositories.catalog import TransportRepository

_DISTANCIAS_KM: dict[tuple[str, str], float] = {
    ("sao paulo", "rio de janeiro"): 435.0,
    ("sao paulo", "curitiba"): 408.0,
    ("sao paulo", "belo horizonte"): 586.0,
    ("sao paulo", "salvador"): 1962.0,
    ("sao paulo", "recife"): 2660.0,
    ("curitiba", "porto alegre"): 711.0,
    ("belo horizonte", "brasilia"): 741.0,
}

_RASTREIOS: dict[str, str] = {
    "GL-1001": "em trânsito — saiu do CD São Paulo, previsão para amanhã",
    "GL-1002": "entregue — recebido por portaria às 14h32",
    "GL-1003": "atrasado — retido em centro de triagem de Curitiba",
}

_DISTANCIA_PADRAO_KM = 900.0
_TARIFA_POR_KM = 2.5
_TARIFA_POR_KG = 1.8
_KM_POR_DIA = 700.0
_STATUS_ATENCAO = ("atras", "trânsito")


def _normalizar(cidade: str) -> str:
    """Normaliza o nome da cidade para busca na tabela de distâncias."""
    return cidade.strip().lower()


def _distancia_km(origem: str, destino: str) -> float:
    """Retorna a distância conhecida entre duas cidades (ou a padrão)."""
    o, d = _normalizar(origem), _normalizar(destino)
    if o == d:
        return 0.0
    return _DISTANCIAS_KM.get((o, d), _DISTANCIAS_KM.get((d, o), _DISTANCIA_PADRAO_KM))


def _texto_frete(origem: str, destino: str, peso_kg: float) -> str:
    """Formata o frete estimado (R$) para a rota e o peso informados."""
    distancia = _distancia_km(origem, destino)
    valor = distancia * _TARIFA_POR_KM + max(peso_kg, 0.0) * _TARIFA_POR_KG
    return (
        f"Frete {origem} -> {destino} | {peso_kg:.1f} kg | "
        f"distância {distancia:.0f} km | R$ {valor:.2f}"
    )


def _texto_prazo(origem: str, destino: str) -> str:
    """Formata o prazo estimado em dias úteis para a rota informada."""
    distancia = _distancia_km(origem, destino)
    prazo = max(1, math.ceil(distancia / _KM_POR_DIA))
    return f"Prazo estimado {origem} -> {destino}: {prazo} dia(s) útil(eis)"


def _exige_atencao(status: str) -> bool:
    """Indica se o status de uma entrega requer atenção operacional."""
    normalizado = status.strip().lower()
    return any(chave in normalizado for chave in _STATUS_ATENCAO)


@tool
def calcular_frete(origem: str, destino: str, peso_kg: float) -> str:
    """Calcula o frete estimado (R$) entre origem e destino para um peso em kg."""
    return _texto_frete(origem, destino, peso_kg)


@tool
def consultar_prazo(origem: str, destino: str) -> str:
    """Estima o prazo de entrega em dias úteis entre origem e destino."""
    return _texto_prazo(origem, destino)


@tool
def rastrear_entrega(codigo: str) -> str:
    """Consulta a situação atual de uma entrega pelo código de rastreio."""
    status = _RASTREIOS.get(codigo.strip().upper())
    if status is None:
        return f"Código {codigo} não encontrado na base de rastreio."
    return f"{codigo}: {status}"


TOOLS = [calcular_frete, consultar_prazo, rastrear_entrega]


def build_transport_tools(
    repo: TransportRepository, empresa_id: UUID
) -> list[BaseTool]:
    """Constrói as tools de transporte amarradas ao repositório do tenant.

    As tools de leitura e análise consultam ``repo`` filtrando por
    ``empresa_id``; ``calcular_frete``/``consultar_prazo`` mantêm o cálculo
    determinístico, preservando as assinaturas chamadas pelo LLM.
    """

    @tool
    def calcular_frete(origem: str, destino: str, peso_kg: float) -> str:
        """Calcula o frete estimado (R$) entre origem e destino para um peso em kg."""
        return _texto_frete(origem, destino, peso_kg)

    @tool
    def consultar_prazo(origem: str, destino: str) -> str:
        """Estima o prazo de entrega em dias úteis entre origem e destino."""
        return _texto_prazo(origem, destino)

    @tool
    def rastrear_entrega(codigo: str) -> str:
        """Consulta a situação atual de uma entrega do tenant pelo código."""
        chave = codigo.strip().upper()
        registro = repo.get_by_codigo(empresa_id, chave)
        if registro is None:
            return f"Código {codigo} não encontrado na base de rastreio."
        return f"{registro.codigo_rastreio}: {registro.status}"

    @tool
    def otimizar_entrega() -> str:
        """Aponta entregas do tenant que exigem atenção (atrasadas ou em trânsito)."""
        registros = repo.list(empresa_id)
        if not registros:
            return "Nenhuma entrega registrada para otimização."
        pendentes = [item for item in registros if _exige_atencao(item.status)]
        if not pendentes:
            return "Nenhuma entrega pendente; operação dentro do esperado."
        linhas = [
            f"{item.codigo_rastreio}: {item.origem} -> {item.destino} | {item.status}"
            for item in pendentes
        ]
        return "Entregas que exigem atenção:\n" + "\n".join(linhas)

    return [calcular_frete, consultar_prazo, rastrear_entrega, otimizar_entrega]
