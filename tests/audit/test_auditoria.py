"""Testes integrados do serviço de auditoria e da política de retenção."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gestlog.audit import (
    EVENTO_CORRECAO_APLICADA,
    EVENTO_CORRECAO_APROVADA,
    EVENTO_CORRECAO_FALHOU,
    EVENTO_CORRECAO_REJEITADA,
    EVENTO_PERGUNTA,
    EVENTOS,
    registrar_evento,
)
from gestlog.audit.retencao import purgar_expiradas, retencao_dias
from gestlog.config import Settings
from gestlog.db.models import Conversation, Feedback, Message, Recommendation
from gestlog.repositories.conversations import (
    ConversationRepository,
    FeedbackRepository,
    MessageRepository,
    RecommendationRepository,
)
from gestlog.repositories.empresas import EmpresaRepository
from gestlog.repositories.telemetry import AuditRepository


def _empresa(session: Session, nome: str, retention_days: int | None = None) -> UUID:
    empresa = EmpresaRepository(session).create(nome, retention_days)
    session.commit()
    return empresa.id


def _conversa_com_dependentes(
    session: Session, empresa_id: UUID, dias_atras: int
) -> tuple[UUID, UUID]:
    momento = datetime.now(UTC) - timedelta(days=dias_atras)
    user_id = uuid4()
    conversa = ConversationRepository(session).create(empresa_id, user_id)
    conversa.created_at = momento
    mensagem = MessageRepository(session).add_message(conversa.id, "user", "oi")
    mensagem.created_at = momento
    recomendacao = RecommendationRepository(session).add_recommendation(
        conversa.id, "estoque", "repor", fontes=["estoque"]
    )
    recomendacao.created_at = momento
    FeedbackRepository(session).add_feedback(recomendacao.id, "aceita", user_id)
    session.commit()
    return conversa.id, recomendacao.id


def _contar(session: Session, model: type) -> int:
    return int(session.execute(select(func.count()).select_from(model)).scalar_one())


def test_registrar_evento_persiste_por_empresa(db_session: Session) -> None:
    empresa = _empresa(db_session, "A")
    outra = _empresa(db_session, "B")

    registrar_evento(
        db_session, empresa, EVENTO_PERGUNTA, detalhe={"dominio": "estoque"}
    )
    db_session.commit()

    eventos = AuditRepository(db_session).list(empresa)
    assert len(eventos) == 1
    assert eventos[0].evento == "pergunta"
    assert eventos[0].detalhe == {"dominio": "estoque"}
    assert AuditRepository(db_session).list(outra) == []


def test_registrar_evento_rejeita_desconhecido(db_session: Session) -> None:
    empresa = _empresa(db_session, "A")

    with pytest.raises(ValueError):
        registrar_evento(db_session, empresa, "inexistente")


_EVENTOS_CORRECAO = (
    EVENTO_CORRECAO_APROVADA,
    EVENTO_CORRECAO_REJEITADA,
    EVENTO_CORRECAO_APLICADA,
    EVENTO_CORRECAO_FALHOU,
)


def test_eventos_de_correcao_estao_no_catalogo() -> None:
    assert set(_EVENTOS_CORRECAO) <= set(EVENTOS)


def test_registrar_eventos_de_correcao_sem_commit(db_session: Session) -> None:
    empresa = _empresa(db_session, "A")

    for evento in _EVENTOS_CORRECAO:
        registrar_evento(
            db_session, empresa, evento, detalhe={"item_id": "abc", "campo": "local"}
        )

    eventos = AuditRepository(db_session).list(empresa)
    assert {registro.evento for registro in eventos} == set(_EVENTOS_CORRECAO)
    assert all(registro.detalhe["campo"] == "local" for registro in eventos)


def test_retencao_usa_prazo_da_empresa(db_session: Session) -> None:
    empresa = EmpresaRepository(db_session).create("A", retention_days=30)
    db_session.commit()

    assert retencao_dias(empresa, Settings(_env_file=None)) == 30


def test_retencao_usa_padrao_quando_empresa_sem_prazo(db_session: Session) -> None:
    empresa = EmpresaRepository(db_session).create("A")
    db_session.commit()
    settings = Settings(_env_file=None, default_retention_days=90)

    assert retencao_dias(empresa, settings) == 90


def test_purga_remove_conversa_e_dependentes(db_session: Session) -> None:
    empresa = _empresa(db_session, "A", retention_days=30)
    conversa_id, recomendacao_id = _conversa_com_dependentes(db_session, empresa, 60)

    removidas = purgar_expiradas(db_session, settings=Settings(_env_file=None))

    assert removidas == 1
    assert _contar(db_session, Conversation) == 0
    assert _contar(db_session, Message) == 0
    assert _contar(db_session, Recommendation) == 0
    assert _contar(db_session, Feedback) == 0
    assert MessageRepository(db_session).list_by_conversation(conversa_id) == []
    assert FeedbackRepository(db_session).list_by_recommendation(recomendacao_id) == []


def test_purga_preserva_dentro_do_prazo(db_session: Session) -> None:
    empresa = _empresa(db_session, "A", retention_days=30)
    _conversa_com_dependentes(db_session, empresa, 10)

    removidas = purgar_expiradas(db_session, settings=Settings(_env_file=None))

    assert removidas == 0
    assert _contar(db_session, Conversation) == 1
    assert _contar(db_session, Message) == 1


def test_purga_isola_entre_empresas(db_session: Session) -> None:
    vencida = _empresa(db_session, "Vencida", retention_days=30)
    retida = _empresa(db_session, "Retida", retention_days=365)
    _conversa_com_dependentes(db_session, vencida, 60)
    _conversa_com_dependentes(db_session, retida, 60)

    removidas = purgar_expiradas(db_session, settings=Settings(_env_file=None))

    assert removidas == 1
    assert len(ConversationRepository(db_session).list(vencida)) == 0
    assert len(ConversationRepository(db_session).list(retida)) == 1


def test_purga_rejeita_datetime_sem_fuso(db_session: Session) -> None:
    _empresa(db_session, "A")

    with pytest.raises(ValueError):
        purgar_expiradas(db_session, agora=datetime(2026, 1, 1))


def test_purga_usa_padrao_do_sistema(db_session: Session) -> None:
    empresa = _empresa(db_session, "A")
    _conversa_com_dependentes(db_session, empresa, 400)
    _conversa_com_dependentes(db_session, empresa, 100)
    settings = Settings(_env_file=None, default_retention_days=365)

    removidas = purgar_expiradas(db_session, settings=settings)

    assert removidas == 1
    assert _contar(db_session, Conversation) == 1
