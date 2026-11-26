"""Política de retenção: purga de conversas, correções e convites além do prazo.

O ``AuditLog`` é deliberadamente **não** purgado (AD-022): ele é a trilha de
conformidade canônica e sobrevive à remoção dos dados operacionais.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from gestlog.config import Settings, get_settings
from gestlog.db.models import Convite, Empresa
from gestlog.repositories.conversations import ConversationRepository
from gestlog.repositories.correcoes import CorrectionRepository
from gestlog.repositories.empresas import EmpresaRepository

logger = logging.getLogger(__name__)


def retencao_dias(empresa: Empresa, settings: Settings | None = None) -> int:
    """Prazo de retenção da empresa, caindo para o padrão quando não definido."""
    if empresa.retention_days is not None:
        return empresa.retention_days
    return (settings or get_settings()).default_retention_days


def purgar_emails_de_convites(
    session: Session, empresa_id: UUID, agora: datetime
) -> int:
    """Zera o e-mail de convites expirados ou já usados (LGPD); mantém a linha.

    A linha do convite é preservada para auditoria (AD-015); só o dado pessoal
    vai embora. Exige ``agora`` com fuso horário para não deslocar o corte
    silenciosamente entre SQLite e Postgres. Devolve quantos convites foram
    zerados; convite já sem e-mail não é recontado.
    """
    if agora.tzinfo is None:
        raise ValueError(
            "purgar_emails_de_convites exige um datetime com fuso horário."
        )
    stmt = (
        update(Convite)
        .where(
            Convite.empresa_id == empresa_id,
            or_(Convite.expira_em <= agora, Convite.usado_em.is_not(None)),
            Convite.email != "",
        )
        .values(email="")
    )
    return int(session.execute(stmt).rowcount or 0)


def purgar_expiradas(
    session: Session,
    agora: datetime | None = None,
    settings: Settings | None = None,
) -> int:
    """Apaga o que passou do prazo de retenção de cada empresa.

    Cada empresa usa o seu próprio prazo (``Empresa.retention_days``) ou o
    padrão do sistema. Remove conversas e seus dependentes **e** os itens de
    correção decididos além do prazo; itens pendentes/abertos são operacionais e
    permanecem. Zera também o e-mail de convites expirados ou já usados,
    preservando a linha para auditoria (PII-02). Empresa com prazo inválido
    (``retention_days <= 0``, possível só em linha legada pré-constraint) não
    tem nada purgado — conversas, correções nem convites (PII-03/EDG-07): a
    purga dela é recusada, o erro é logado e as demais empresas seguem.
    Devolve o total de registros removidos/zerados e confirma a transação ao
    final. Exige ``agora`` com fuso horário para não deslocar o corte
    silenciosamente entre SQLite e Postgres. O ``AuditLog`` não é purgado
    (AD-022).
    """
    momento = agora or datetime.now(UTC)
    if momento.tzinfo is None:
        raise ValueError("purgar_expiradas exige um datetime com fuso horário.")
    conversas = ConversationRepository(session)
    correcoes = CorrectionRepository(session)
    total = 0
    for empresa in EmpresaRepository(session).list_all():
        dias = retencao_dias(empresa, settings)
        if dias <= 0:
            logger.error(
                "retention_days inválido (%s) na empresa %s; purga recusada",
                dias,
                empresa.id,
            )
            continue
        limite = momento - timedelta(days=dias)
        total += conversas.purgar_expiradas(empresa.id, limite)
        total += correcoes.purgar_expiradas(empresa.id, limite)
        total += purgar_emails_de_convites(session, empresa.id, momento)
    session.commit()
    return total
