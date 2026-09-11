"""Testes dos repositórios com escopo de tenant."""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from gestlog.repositories.catalog import (
    StockRepository,
    SupplierRepository,
    TransportRepository,
)
from gestlog.repositories.conversations import (
    ConversationRepository,
    FeedbackRepository,
    MessageRepository,
    RecommendationRepository,
)
from gestlog.repositories.imports import ImportJobRepository
from gestlog.repositories.telemetry import AuditRepository, UsageRepository
from gestlog.repositories.tenants import MembershipRepository, TenantRepository


def _dois_tenants(session: Session) -> tuple[UUID, UUID]:
    repo = TenantRepository(session)
    t1 = repo.create("A")
    t2 = repo.create("B")
    session.commit()
    return t1.id, t2.id


def test_stock_isolado_por_tenant(db_session: Session) -> None:
    t1, t2 = _dois_tenants(db_session)
    repo = StockRepository(db_session)
    item = repo.upsert(t1, "SKU-1", "Caixa", 10, 5, "A1")
    db_session.commit()

    assert len(repo.list(t1)) == 1
    assert repo.list(t2) == []
    assert repo.get(t2, item.id) is None
    assert repo.get_by_sku(t2, "SKU-1") is None


def test_stock_upsert_atualiza(db_session: Session) -> None:
    t1, _ = _dois_tenants(db_session)
    repo = StockRepository(db_session)
    repo.upsert(t1, "SKU-1", "Caixa", 10, 5, "A1")
    item = repo.upsert(t1, "SKU-1", "Caixa grande", 99, 5, "A2")
    db_session.commit()

    assert item.quantidade == 99
    assert item.nome == "Caixa grande"
    assert len(repo.list(t1)) == 1


def test_supplier_upsert_e_busca(db_session: Session) -> None:
    t1, t2 = _dois_tenants(db_session)
    repo = SupplierRepository(db_session)
    repo.upsert(t1, "F-1", "TransLog", "transporte", 5, 4.5, True)
    db_session.commit()

    assert repo.get_by_fornecedor_id(t1, "f-1") is not None
    assert repo.get_by_fornecedor_id(t2, "F-1") is None


def test_transport_upsert_e_busca(db_session: Session) -> None:
    t1, t2 = _dois_tenants(db_session)
    repo = TransportRepository(db_session)
    repo.upsert(t1, "GL-1", "SP", "CWB", 10.0, "em trânsito")
    db_session.commit()

    assert repo.get_by_codigo(t1, "gl-1") is not None
    assert repo.get_by_codigo(t2, "GL-1") is None


def test_import_job_com_erros(db_session: Session) -> None:
    t1, t2 = _dois_tenants(db_session)
    repo = ImportJobRepository(db_session)
    job = repo.create_job(t1, "estoque")
    repo.add_error(job, linha=2, motivo="sku ausente")
    repo.finish(job, aceitas=3)
    db_session.commit()

    assert job.rejeitadas == 1
    assert job.aceitas == 3
    assert job.status == "concluido"
    assert repo.list(t2) == []


def test_usage_total_por_tenant(db_session: Session) -> None:
    t1, t2 = _dois_tenants(db_session)
    repo = UsageRepository(db_session)
    repo.record(t1, "qwen", 100)
    repo.record(t1, "qwen", 50)
    repo.record(t2, "qwen", 10)
    db_session.commit()

    assert repo.total_tokens(t1) == 150
    assert repo.total_tokens(t2) == 10


def test_audit_record_e_list(db_session: Session) -> None:
    t1, t2 = _dois_tenants(db_session)
    repo = AuditRepository(db_session)
    repo.record(t1, "login", detalhe={"ip": "127.0.0.1"})
    db_session.commit()

    eventos = repo.list(t1)
    assert len(eventos) == 1
    assert eventos[0].evento == "login"
    assert repo.list(t2) == []


def test_membership_add_e_by_user(db_session: Session) -> None:
    t1, _ = _dois_tenants(db_session)
    user_id = uuid4()
    repo = MembershipRepository(db_session)
    repo.add_member(t1, user_id, papel="admin")
    db_session.commit()

    vinculos = repo.by_user(user_id)
    assert len(vinculos) == 1
    assert vinculos[0].papel == "admin"
    assert repo.list(t1)[0].user_id == user_id


def test_conversas_mensagens_recomendacoes_feedback(db_session: Session) -> None:
    t1, _ = _dois_tenants(db_session)
    user_id = uuid4()
    conv_repo = ConversationRepository(db_session)
    conversa = conv_repo.create(t1, user_id)

    msg_repo = MessageRepository(db_session)
    msg_repo.add_message(conversa.id, "user", "quanto repor?")
    msg_repo.add_message(conversa.id, "assistant", "reponha 100")
    rec_repo = RecommendationRepository(db_session)
    rec = rec_repo.add_recommendation(
        conversa.id, "estoque", "repor 100", "abaixo do mínimo"
    )
    FeedbackRepository(db_session).add_feedback(rec.id, "aceita", user_id)
    db_session.commit()

    assert len(msg_repo.list_by_conversation(conversa.id)) == 2
    assert len(rec_repo.list_by_conversation(conversa.id)) == 1
    assert rec.fontes is None
