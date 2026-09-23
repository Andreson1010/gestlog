"""Regras de completude cadastral por tipo (vazio/zero/default = ausente)."""

from __future__ import annotations

from gestlog.db.models import StockItem, Supplier, TransportRecord

Registro = StockItem | Supplier | TransportRecord

_CAMPOS: dict[str, dict[str, str]] = {
    "estoque": {"nome": "texto", "minimo": "inteiro", "local": "texto"},
    "fornecedores": {
        "nome": "texto",
        "categoria": "texto",
        "prazo_dias": "inteiro",
        "avaliacao": "decimal",
    },
    "transporte": {
        "origem": "texto",
        "destino": "texto",
        "peso_kg": "decimal",
        "status": "texto",
    },
}


class TipoCorrecaoInvalido(ValueError):
    """Tipo de cadastro não coberto pelas regras de completude."""

    def __init__(self, tipo: str) -> None:
        super().__init__(f"Tipo de correção desconhecido: {tipo}")
        self.tipo = tipo


class CampoCorrecaoInvalido(ValueError):
    """Campo não verificado pela tabela de completude do tipo."""

    def __init__(self, tipo: str, campo: str) -> None:
        super().__init__(f"Campo de correção desconhecido para {tipo}: {campo}")
        self.tipo = tipo
        self.campo = campo


def _campos(tipo: str) -> dict[str, str]:
    """Devolve a tabela campo->natureza do tipo, recusando tipos desconhecidos."""
    try:
        return _CAMPOS[tipo]
    except KeyError as erro:
        raise TipoCorrecaoInvalido(tipo) from erro


def _ausente(valor: object, natureza: str) -> bool:
    """Diz se o valor conta como ausente conforme a natureza do campo."""
    if natureza == "texto":
        return not str(valor or "").strip()
    if natureza == "inteiro":
        return int(valor or 0) <= 0
    return float(valor or 0.0) <= 0.0


def _serializar(valor: object, natureza: str) -> str:
    """Serializa o valor em string canônica para comparação de conflito."""
    if natureza == "inteiro":
        return str(int(valor or 0))
    if natureza == "decimal":
        return str(float(valor or 0.0))
    return "" if valor is None else str(valor)


def campos_faltantes(tipo: str, registro: Registro) -> list[str]:
    """Lista, na ordem do design, os campos ausentes do registro."""
    return [
        campo
        for campo, natureza in _campos(tipo).items()
        if _ausente(getattr(registro, campo), natureza)
    ]


def valor_atual(tipo: str, registro: Registro, campo: str) -> str:
    """Serializa o valor atual do campo para o snapshot de conflito."""
    naturezas = _campos(tipo)
    if campo not in naturezas:
        raise CampoCorrecaoInvalido(tipo, campo)
    return _serializar(getattr(registro, campo), naturezas[campo])
