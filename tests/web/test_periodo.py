"""Testes do recorte de período UTC compartilhado entre os routers web."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from gestlog.web.periodo import fim_do_dia, inicio_do_dia


def test_inicio_do_dia_retorna_primeiro_instante_em_utc() -> None:
    assert inicio_do_dia(date(2026, 6, 10)) == datetime(
        2026, 6, 10, 0, 0, 0, tzinfo=UTC
    )


def test_fim_do_dia_retorna_ultimo_instante_em_utc() -> None:
    esperado = datetime.combine(date(2026, 6, 10), time.max, tzinfo=UTC)
    assert fim_do_dia(date(2026, 6, 10)) == esperado


def test_inicio_do_dia_ausente_permanece_none() -> None:
    assert inicio_do_dia(None) is None


def test_fim_do_dia_ausente_permanece_none() -> None:
    assert fim_do_dia(None) is None


def test_mesmo_dia_produz_recorte_inclusivo() -> None:
    dia = date(2026, 6, 10)
    assert inicio_do_dia(dia) < fim_do_dia(dia)
