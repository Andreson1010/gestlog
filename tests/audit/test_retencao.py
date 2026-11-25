"""Testes da política de retenção: purga de convites e fail-safe do prazo."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from apoio import criar_usuario
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gestlog.audit.retencao import (
    purgar_expiradas,
    purgar_emails_de_convites,
    retencao_dias,
)
from gestlog.config import Settings
from gestlog.db.models import Convite, Empresa
from gestlog.repositories.conversations import ConversationRepository
from gestlog.repositories.empresas import EmpresaRepository

_PASTADO = datetime.now(UTC) - timedelta(days=1)


def _empresa(session: Session, nome: str) -> Empresa:
    empresa = EmpresaRepository(session).create(nome)
    session.commit()
    return empresa


def _convite(
    session: Session,
    empresa_id: UUID,
    *,
    email: str = "convidado@x.com",
    expira_em: datetime | None = None,
    usado_em: datetime | None = None,
) -> Convite:
    convite = Convite(
        empresa_id=empresa_id,
        email=email,
        papel="operador",
        token_hash=uuid4().hex,
        expira_em=expira_em or datetime.now(UTC) + timedelta(days=7),
        usado_em=usado_em,
    )
    session.add(convite)
    session.commit()
    return convite


def _conversa_antiga(session: Session, empresa_id: UUID) -> None:
    """Conversa criada além de qualquer prazo, alvo imediato da purga."""
    conversa = ConversationRepository(session).create(empresa_id, criar_usuario(session))
    conversa.created_at = datetime.now(UTC) - timedelta(days=60)
    session.commit()


def _emails_de_convites(session: Session) -> dict[UUID, str]:
    """E-mails de todos os convites, lidos do banco (sem cache do ORM)."""
    return dict(session.execute(select(Convite.id, Convite.email)).all())


def _contar_convites(session: Session) -> int:
    return int(session.execute(select(func.count()).select_from(Convite)).scalar_one())


def test_purga_zera_email_de_convites_expirados_e_usados(db_session: Session) -> None:
    """PII-02: expirado e usado perdem o e-mail; válido e a linha permanecem."""
    empresa = _empresa(db_session, "A")
    expirado = _convite(db_session, empresa.id, expira_em=_PASTADO)
    usado = _convite(db_session, empresa.id, usado_em=_PASTADO)
    valido = _convite(db_session, empresa.id)

    removidas = purgar_expiradas(db_session, settings=Settings(_env_file=None))

    assert removidas == 2
    emails = _emails_de_convites(db_session)
    assert emails[expirado.id] == ""
    assert emails[usado.id] == ""
    assert emails[valido.id] == "convidado@x.com"
    assert _contar_convites(db_session) == 3


def test_retention_days_zero_recusa_purga_e_loga_erro(
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PII-03/EDG-07: prazo inválido congela a empresa; as demais seguem.

    A constraint (PII-04) impede persistir ``retention_days <= 0`` — linhas
    legadas com prazo inválido só existem em bancos pré-migração; o prazo é
    simulado em ``retencao_dias`` para exercitar o guard da rotina.
    """
    congelada = _empresa(db_session, "Congelada")
    normal_repo = EmpresaRepository(db_session)
    normal = normal_repo.create("Normal", retention_days=30)
    db_session.commit()
    _conversa_antiga(db_session, congelada.id)
    _conversa_antiga(db_session, normal.id)
    convite_congelada = _convite(db_session, congelada.id, expira_em=_PASTADO)
    convite_normal = _convite(db_session, normal.id, expira_em=_PASTADO)
    original = retencao_dias

    def prazo_legado(empresa: Empresa, settings: Settings | None = None) -> int:
        if empresa.id == congelada.id:
            return 0
        return original(empresa, settings)

    monkeypatch.setattr("gestlog.audit.retencao.retencao_dias", prazo_legado)

    with caplog.at_level(logging.ERROR, logger="gestlog.audit.retencao"):
        removidas = purgar_expiradas(db_session, settings=Settings(_env_file=None))

    assert removidas == 2
    assert "purga recusada" in caplog.text
    assert str(congelada.id) in caplog.text
    assert len(ConversationRepository(db_session).list(congelada.id)) == 1
    assert len(ConversationRepository(db_session).list(normal.id)) == 0
    emails = _emails_de_convites(db_session)
    assert emails[convite_congelada.id] == "convidado@x.com"
    assert emails[convite_normal.id] == ""


def test_purgar_emails_de_convites_nao_recontar_email_ja_vazio(
    db_session: Session,
) -> None:
    """Convite já sem e-mail não é recontado na purga (idempotente)."""
    empresa = _empresa(db_session, "A")
    _convite(db_session, empresa.id, email="", expira_em=_PASTADO)
    com_email = _convite(db_session, empresa.id, expira_em=_PASTADO)
    agora = datetime.now(UTC)

    primeira = purgar_emails_de_convites(db_session, empresa.id, agora)
    segunda = purgar_emails_de_convites(db_session, empresa.id, agora)

    assert primeira == 1
    assert segunda == 0
    assert _emails_de_convites(db_session)[com_email.id] == ""


def test_purgar_emails_de_convites_rejeita_datetime_sem_fuso(
    db_session: Session,
) -> None:
    empresa = _empresa(db_session, "A")

    with pytest.raises(ValueError):
        purgar_emails_de_convites(db_session, empresa.id, datetime(2026, 1, 1))
