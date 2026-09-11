"""Ferramentas do especialista em transporte.

Dados mockados e determinísticos: servem de andaime até a integração com o TMS.
"""

from __future__ import annotations

import math

from langchain_core.tools import tool

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


def _normalizar(cidade: str) -> str:
    return cidade.strip().lower()


def _distancia_km(origem: str, destino: str) -> float:
    o, d = _normalizar(origem), _normalizar(destino)
    if o == d:
        return 0.0
    return _DISTANCIAS_KM.get((o, d), _DISTANCIAS_KM.get((d, o), 900.0))


@tool
def calcular_frete(origem: str, destino: str, peso_kg: float) -> str:
    """Calcula o frete estimado (R$) entre origem e destino para um peso em kg."""
    distancia = _distancia_km(origem, destino)
    valor = distancia * 2.5 + max(peso_kg, 0.0) * 1.8
    return (
        f"Frete {origem} -> {destino} | {peso_kg:.1f} kg | "
        f"distância {distancia:.0f} km | R$ {valor:.2f}"
    )


@tool
def consultar_prazo(origem: str, destino: str) -> str:
    """Estima o prazo de entrega em dias úteis entre origem e destino."""
    distancia = _distancia_km(origem, destino)
    prazo = max(1, math.ceil(distancia / 700.0))
    return f"Prazo estimado {origem} -> {destino}: {prazo} dia(s) útil(eis)"


@tool
def rastrear_entrega(codigo: str) -> str:
    """Consulta a situação atual de uma entrega pelo código de rastreio."""
    status = _RASTREIOS.get(codigo.strip().upper())
    if status is None:
        return f"Código {codigo} não encontrado na base de rastreio."
    return f"{codigo}: {status}"


TOOLS = [calcular_frete, consultar_prazo, rastrear_entrega]
