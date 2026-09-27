"""Geração determinística de sugestões a partir dos dados do próprio tenant."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from math import floor

from gestlog.correcoes.completude import Registro, natureza, serializar

_ESTRATEGIAS: dict[str, dict[str, str]] = {
    "estoque": {"minimo": "mediana_inteiro", "local": "moda"},
    "fornecedores": {
        "categoria": "moda",
        "prazo_dias": "mediana_inteiro",
        "avaliacao": "media_decimal",
    },
    "transporte": {"origem": "moda", "destino": "moda", "status": "moda"},
}

_FONTES: dict[tuple[str, str], str] = {
    ("estoque", "minimo"): "estoque mínimo mediano dos itens",
    ("estoque", "local"): "local mais comum nos itens",
    ("fornecedores", "categoria"): "categoria mais comum entre {n} fornecedores",
    ("fornecedores", "prazo_dias"): "prazo mediano dos fornecedores",
    ("fornecedores", "avaliacao"): "avaliação média dos fornecedores",
    ("transporte", "origem"): "origem mais frequente nos registros",
    ("transporte", "destino"): "destino mais frequente nos registros",
    ("transporte", "status"): "status mais frequente nos registros",
}

_SEM_BASE = "sem base de dados no tenant"


@dataclass(frozen=True)
class Sugestao:
    """Sugestão determinística de preenchimento de um campo faltante."""

    campo: str
    valor: str | None
    justificativa: str
    fonte: str


def _sem_sugestao(campo: str) -> Sugestao:
    """Sugestão vazia: não há base no tenant, nada é inventado."""
    return Sugestao(campo=campo, valor=None, justificativa=_SEM_BASE, fonte="")


def _valores_texto(demais: Sequence[Registro], campo: str) -> list[str]:
    """Valores textuais não vazios, normalizados por ``strip``."""
    textos = []
    for registro in demais:
        texto = str(getattr(registro, campo) or "").strip()
        if texto:
            textos.append(texto)
    return textos


def _valores_positivos(demais: Sequence[Registro], campo: str) -> list[float]:
    """Valores numéricos estritamente positivos (zero é ausente)."""
    numeros = []
    for registro in demais:
        numero = float(getattr(registro, campo) or 0)
        if numero > 0:
            numeros.append(numero)
    return numeros


def _valores(
    demais: Sequence[Registro], campo: str, estrategia: str
) -> list[str] | list[float]:
    """Valores de base conforme a estratégia da sugestão."""
    if estrategia == "moda":
        return _valores_texto(demais, campo)
    return _valores_positivos(demais, campo)


def _moda(valores: list[str]) -> str:
    """Valor mais frequente; empate resolvido pelo menor lexicográfico."""
    contagem = Counter(valores)
    maximo = max(contagem.values())
    return min(valor for valor, qtd in contagem.items() if qtd == maximo)


def _mediana_inteiro(valores: list[float]) -> int:
    """Mediana inteira; quantidade par arredonda a média central para cima."""
    ordenados = sorted(valores)
    metade = len(ordenados) // 2
    if len(ordenados) % 2:
        return int(ordenados[metade])
    return int(floor((ordenados[metade - 1] + ordenados[metade]) / 2 + 0.5))


def _media_decimal(valores: list[float]) -> float:
    """Média arredondada para uma casa decimal."""
    return round(sum(valores) / len(valores), 1)


def _justificativa(campo: str, estrategia: str, valor: object, n: int) -> str:
    """Texto explicativo da estratégia usada."""
    if estrategia == "moda":
        return f"{valor} é o valor mais frequente entre {n} registros do tenant"
    if estrategia == "mediana_inteiro":
        return f"mediana dos {campo} acima de zero entre {n} registros"
    return f"média dos {campo} acima de zero entre {n} registros"


def _fonte(tipo: str, campo: str, n: int) -> str:
    """Rótulo da fonte/dado que sustenta a sugestão."""
    template = _FONTES.get((tipo, campo), "")
    return template.format(n=n) if "{n}" in template else template


def sugerir(
    tipo: str,
    campo: str,
    registro: Registro,
    contexto: Sequence[Registro],
) -> Sugestao:
    """Sugere um valor para o campo a partir dos demais registros do tenant.

    ``contexto`` reúne os registros do mesmo tipo no tenant; o próprio alvo é
    ignorado por identidade. Sem estratégia ou sem base, devolve uma sugestão
    sem valor (nunca inventa).
    """
    natureza(tipo, campo)
    estrategia = _ESTRATEGIAS.get(tipo, {}).get(campo)
    if estrategia is None:
        return _sem_sugestao(campo)
    demais = [outro for outro in contexto if outro is not registro]
    valores = _valores(demais, campo, estrategia)
    if not valores:
        return _sem_sugestao(campo)
    if estrategia == "moda":
        valor: object = _moda(valores)
    elif estrategia == "mediana_inteiro":
        valor = _mediana_inteiro(valores)
    else:
        valor = _media_decimal(valores)
    return Sugestao(
        campo=campo,
        valor=serializar(tipo, campo, valor),
        justificativa=_justificativa(campo, estrategia, valor, len(valores)),
        fonte=_fonte(tipo, campo, len(valores)),
    )
