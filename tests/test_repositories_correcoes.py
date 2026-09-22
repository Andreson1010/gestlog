"""Testes do repositório de correções com escopo de empresa."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from gestlog.db.models import ItemCorrecao
from gestlog.repositories.correcoes import CorrectionRepository
from gestlog.repositories.empresas import EmpresaRepository


def _empresas(session: Session) -> tuple[UUID, UUID]:
    repo = EmpresaRepository(session)
    t1 = repo.create("A")
    t2 = repo.create("B")
    session.commit()
    return t1.id, t2.id


def _item(
    session: Session,
    empresa_id: UUID,
    *,
    status: str = "pendente",
    tipo: str = "estoque",
    alvo_chave: str = "SKU-1",
    campo: str = "minimo",
    valor_no_pedido: str = "0",
    valor_sugerido: str | None = "5",
    created_at: datetime | None = None,
    decidido_em: datetime | None = None,
) -> ItemCorrecao:
    item = ItemCorrecao(
        empresa_id=empresa_id,
        tipo=tipo,
        alvo_chave=alvo_chave,
        campo=campo,
        valor_no_pedido=valor_no_pedido,
        valor_sugerido=valor_sugerido,
        justificativa="justificativa de teste",
        fonte="fonte de teste",
        status=status,
        created_at=created_at or datetime.now(UTC),
        decidido_em=decidido_em,
    )
    session.add(item)
    session.flush()
    return item


def test_correcoes_isoladas_por_empresa(db_session: Session) -> None:
    t1, t2 = _empresas(db_session)
    repo = CorrectionRepository(db_session)
    item = _item(db_session, t1)
    db_session.commit()

    assert repo.list_by_status(t1, "pendente") == [item]
    assert repo.list_by_status(t2, "pendente") == []
    assert repo.get(t2, item.id) is None
    assert repo.abertos_para(t2, "estoque", "SKU-1", "minimo") == []
    assert repo.existe_para(t2, "estoque", "SKU-1", "minimo", "0") is False
    assert repo.listar_trilha(t2) == []


def test_list_by_status_ordena_por_criacao(db_session: Session) -> None:
    t1, _ = _empresas(db_session)
    repo = CorrectionRepository(db_session)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    segundo = _item(
        db_session, t1, alvo_chave="SKU-2", created_at=base + timedelta(hours=1)
    )
    primeiro = _item(db_session, t1, alvo_chave="SKU-1", created_at=base)
    _item(db_session, t1, status="aplicado")
    db_session.commit()

    pendentes = repo.list_by_status(t1, "pendente")
    assert [item.id for item in pendentes] == [primeiro.id, segundo.id]


def test_existe_para_considera_valor_no_pedido(db_session: Session) -> None:
    t1, _ = _empresas(db_session)
    repo = CorrectionRepository(db_session)
    _item(db_session, t1, valor_no_pedido="0")
    db_session.commit()

    assert repo.existe_para(t1, "estoque", "SKU-1", "minimo", "0") is True
    assert repo.existe_para(t1, "estoque", "SKU-1", "minimo", "9") is False
    assert repo.existe_para(t1, "estoque", "SKU-1", "local", "0") is False


def test_abertos_para_inclui_pendente_e_aprovado(db_session: Session) -> None:
    t1, _ = _empresas(db_session)
    repo = CorrectionRepository(db_session)
    pendente = _item(db_session, t1, status="pendente")
    aprovado = _item(db_session, t1, status="aprovado", alvo_chave="SKU-2")
    _item(db_session, t1, status="aplicado", alvo_chave="SKU-3")
    _item(db_session, t1, status="rejeitado", alvo_chave="SKU-4")
    db_session.commit()

    abertos = repo.abertos_para(t1, "estoque", "SKU-1", "minimo")
    abertos += repo.abertos_para(t1, "estoque", "SKU-2", "minimo")
    assert {item.id for item in abertos} == {pendente.id, aprovado.id}


def test_listar_trilha_filtra_ordena_e_limita(db_session: Session) -> None:
    t1, _ = _empresas(db_session)
    repo = CorrectionRepository(db_session)
    base = datetime(2026, 3, 1, tzinfo=UTC)
    antigo = _item(
        db_session,
        t1,
        status="aplicado",
        alvo_chave="SKU-1",
        decidido_em=base,
    )
    meio = _item(
        db_session,
        t1,
        status="falhou",
        alvo_chave="SKU-2",
        decidido_em=base + timedelta(days=1),
    )
    novo = _item(
        db_session,
        t1,
        status="aplicado",
        alvo_chave="SKU-3",
        decidido_em=base + timedelta(days=2),
    )
    _item(db_session, t1, status="pendente", alvo_chave="SKU-4")
    db_session.commit()

    trilha = repo.listar_trilha(t1)
    assert [item.id for item in trilha] == [novo.id, meio.id, antigo.id]

    filtrada = repo.listar_trilha(
        t1, desde=base + timedelta(hours=12), ate=base + timedelta(days=1, hours=12)
    )
    assert [item.id for item in filtrada] == [meio.id]

    limitada = repo.listar_trilha(t1, limite=2)
    assert [item.id for item in limitada] == [novo.id, meio.id]


def test_listar_trilha_ignora_rejeitado(db_session: Session) -> None:
    t1, _ = _empresas(db_session)
    repo = CorrectionRepository(db_session)
    base = datetime(2026, 4, 1, tzinfo=UTC)
    aplicado = _item(
        db_session, t1, status="aplicado", alvo_chave="SKU-1", decidido_em=base
    )
    _item(db_session, t1, status="rejeitado", alvo_chave="SKU-2", decidido_em=base)
    db_session.commit()

    trilha = repo.listar_trilha(t1)

    assert [item.id for item in trilha] == [aplicado.id]


def test_purgar_expiradas_remove_so_decididos(db_session: Session) -> None:
    t1, t2 = _empresas(db_session)
    repo = CorrectionRepository(db_session)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    antigo = base
    _item(db_session, t1, status="rejeitado", created_at=antigo)
    _item(db_session, t1, status="aplicado", created_at=antigo)
    _item(db_session, t1, status="falhou", created_at=antigo)
    _item(db_session, t1, status="pendente", created_at=antigo)
    _item(db_session, t1, status="aprovado", created_at=antigo)
    recente = _item(
        db_session,
        t1,
        status="aplicado",
        alvo_chave="SKU-9",
        created_at=base + timedelta(days=10),
    )
    _item(db_session, t2, status="aplicado", created_at=antigo)
    db_session.commit()

    removidos = repo.purgar_expiradas(t1, base + timedelta(days=5))
    db_session.commit()

    assert removidos == 3
    restantes = {item.status for item in repo.list(t1)}
    assert restantes == {"pendente", "aprovado", "aplicado"}
    assert len(repo.list(t1)) == 3
    assert repo.get(t1, recente.id) is not None
    assert len(repo.list(t2)) == 1
    assert repo.purgar_expiradas(t2, base) == 0
