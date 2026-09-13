"""Validação e normalização de linhas importadas por tipo."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal, InvalidOperation

from gestlog.ingestion.erros import (
    ArquivoVazio,
    ColunasFaltando,
    TipoImportacaoInvalido,
)
from gestlog.ingestion.modelos import (
    ErroLinha,
    RegistroEstoque,
    RegistroFornecedor,
    RegistroTransporte,
    ResultadoImportacao,
)
from gestlog.ingestion.tabela import ler_tabela

COLUNAS_OBRIGATORIAS: dict[str, tuple[str, ...]] = {
    "estoque": ("sku", "nome", "quantidade", "minimo"),
    "fornecedores": ("fornecedor_id", "nome"),
    "transporte": ("codigo_rastreio", "origem", "destino", "peso_kg"),
}

_VALORES_VERDADE = {"1", "true", "sim", "s", "yes", "y"}
_VALORES_FALSO = {"0", "false", "nao", "não", "n", "no"}


def analisar(tipo: str, conteudo: bytes, nome_arquivo: str = "") -> ResultadoImportacao:
    """Valida e normaliza um arquivo do ``tipo``, separando erros por linha."""
    validador = _VALIDADORES.get(tipo)
    if validador is None:
        raise TipoImportacaoInvalido(tipo)
    if not conteudo:
        raise ArquivoVazio()
    cabecalho, linhas = ler_tabela(conteudo, nome_arquivo)
    faltando = [c for c in COLUNAS_OBRIGATORIAS[tipo] if c not in cabecalho]
    if faltando:
        raise ColunasFaltando(tipo, faltando)
    registros = []
    erros = []
    for numero, bruto in linhas:
        resultado = validador(numero, bruto)
        if isinstance(resultado, ErroLinha):
            erros.append(resultado)
        else:
            registros.append(resultado)
    return ResultadoImportacao(tipo, tuple(registros), tuple(erros))


def _estoque(linha: int, bruto: dict[str, str]) -> RegistroEstoque | ErroLinha:
    try:
        return RegistroEstoque(
            sku=_texto_obrigatorio(bruto, "sku").upper(),
            nome=_texto_obrigatorio(bruto, "nome"),
            quantidade=_inteiro(bruto, "quantidade"),
            minimo=_inteiro(bruto, "minimo"),
            local=_texto(bruto, "local"),
        )
    except ValueError as exc:
        return ErroLinha(linha, str(exc))


def _fornecedor(linha: int, bruto: dict[str, str]) -> RegistroFornecedor | ErroLinha:
    try:
        return RegistroFornecedor(
            fornecedor_id=_texto_obrigatorio(bruto, "fornecedor_id").upper(),
            nome=_texto_obrigatorio(bruto, "nome"),
            categoria=_texto(bruto, "categoria"),
            prazo_dias=_inteiro(bruto, "prazo_dias", default=0),
            avaliacao=_decimal(bruto, "avaliacao", default=0.0),
            ativo=_booleano(bruto, "ativo", default=True),
        )
    except ValueError as exc:
        return ErroLinha(linha, str(exc))


def _transporte(linha: int, bruto: dict[str, str]) -> RegistroTransporte | ErroLinha:
    try:
        return RegistroTransporte(
            codigo_rastreio=_texto_obrigatorio(bruto, "codigo_rastreio").upper(),
            origem=_texto_obrigatorio(bruto, "origem"),
            destino=_texto_obrigatorio(bruto, "destino"),
            peso_kg=_decimal(bruto, "peso_kg"),
            status=_texto(bruto, "status"),
        )
    except ValueError as exc:
        return ErroLinha(linha, str(exc))


_VALIDADORES: dict[str, Callable[[int, dict[str, str]], object]] = {
    "estoque": _estoque,
    "fornecedores": _fornecedor,
    "transporte": _transporte,
}


def _texto(bruto: dict[str, str], campo: str) -> str:
    return str(bruto.get(campo, "") or "").strip()


def _texto_obrigatorio(bruto: dict[str, str], campo: str) -> str:
    valor = _texto(bruto, campo)
    if not valor:
        raise ValueError(f"campo obrigatório '{campo}' vazio")
    return valor


def _inteiro(bruto: dict[str, str], campo: str, default: int | None = None) -> int:
    valor = _texto(bruto, campo)
    if not valor:
        if default is not None:
            return default
        raise ValueError(f"campo obrigatório '{campo}' vazio")
    numero = _para_decimal(valor, campo)
    if not numero.is_integer():
        raise ValueError(f"'{campo}' deve ser inteiro (valor: {valor!r})")
    inteiro = int(numero)
    if inteiro < 0:
        raise ValueError(f"'{campo}' deve ser >= 0 (valor: {inteiro})")
    return inteiro


def _decimal(bruto: dict[str, str], campo: str, default: float | None = None) -> float:
    valor = _texto(bruto, campo)
    if not valor:
        if default is not None:
            return default
        raise ValueError(f"campo obrigatório '{campo}' vazio")
    numero = _para_decimal(valor, campo)
    if numero < 0:
        raise ValueError(f"'{campo}' deve ser >= 0 (valor: {valor!r})")
    return float(numero)


def _booleano(bruto: dict[str, str], campo: str, default: bool = True) -> bool:
    valor = _texto(bruto, campo).lower()
    if not valor:
        return default
    if valor in _VALORES_VERDADE:
        return True
    if valor in _VALORES_FALSO:
        return False
    raise ValueError(f"'{campo}' deve ser booleano (valor: {valor!r})")


def _para_decimal(valor: str, campo: str) -> float:
    try:
        return float(Decimal(valor.replace(",", ".")))
    except InvalidOperation as exc:
        raise ValueError(f"'{campo}' deve ser numérico (valor: {valor!r})") from exc
