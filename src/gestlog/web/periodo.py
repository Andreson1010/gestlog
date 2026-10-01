"""Recorte de período por data, em UTC (primeiro/último instante do dia)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time


def inicio_do_dia(valor: date | None) -> datetime | None:
    """Converte a data no primeiro instante do dia (UTC); ``None`` permanece."""
    return datetime.combine(valor, time.min, tzinfo=UTC) if valor else None


def fim_do_dia(valor: date | None) -> datetime | None:
    """Converte a data no último instante do dia (UTC); ``None`` permanece."""
    return datetime.combine(valor, time.max, tzinfo=UTC) if valor else None
