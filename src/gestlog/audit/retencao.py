"""Política de retenção: purga de conversas além do prazo por empresa."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from gestlog.config import Settings, get_settings
from gestlog.db.models import Empresa
from gestlog.repositories.conversations import ConversationRepository
from gestlog.repositories.empresas import EmpresaRepository


def retencao_dias(empresa: Empresa, settings: Settings | None = None) -> int:
    """Prazo de retenção da empresa, caindo para o padrão quando não definido."""
    if empresa.retention_days is not None:
        return empresa.retention_days
    return (settings or get_settings()).default_retention_days


def purgar_expiradas(
    session: Session,
    agora: datetime | None = None,
    settings: Settings | None = None,
) -> int:
    """Apaga o que passou do prazo de retenção de cada empresa.

    Cada empresa usa o seu próprio prazo (``Empresa.retention_days``) ou o
    padrão do sistema. Devolve o total de conversas removidas e confirma a
    transação ao final. Exige ``agora`` com fuso horário para não deslocar o
    corte silenciosamente entre SQLite e Postgres.
    """
    momento = agora or datetime.now(UTC)
    if momento.tzinfo is None:
        raise ValueError("purgar_expiradas exige um datetime com fuso horário.")
    repositorio = ConversationRepository(session)
    total = 0
    for empresa in EmpresaRepository(session).list_all():
        limite = momento - timedelta(days=retencao_dias(empresa, settings))
        total += repositorio.purgar_expiradas(empresa.id, limite)
    session.commit()
    return total
