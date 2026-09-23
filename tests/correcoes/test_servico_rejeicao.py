"""Testes de integração da rejeição de correções com justificativa (T8)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from gestlog.audit import EVENTO_CORRECAO_REJEITADA
from gestlog.correcoes.erros import (
    CorrecaoNaoAprovavel,
    CorrecaoNaoEncontrada,
    JustificativaObrigatoria,
)
from gestlog.correcoes.servico import CorrectionService
from gestlog.db.models import ItemCorrecao
from gestlog.repositories.catalog import StockRepository
from gestlog.repositories.correcoes import CorrectionRepository
from gestlog.repositories.empresas import EmpresaRepository
from gestlog.repositories.telemetry import AuditRepository


def _empresas(session: Session) -> tuple[UUID, UUID]:
    repo = EmpresaRepository(session)
    a = repo.create("A")
    b = repo.create("B")
    session.commit()
    return a.id, b.id


def _item(
    session: Session,
    empresa_id: UUID,
    *,
    status: str = "pendente",
    campo: str = "minimo",
    alvo_chave: str = "SKU-1",
    valor_sugerido: str | None = "9",
) -> ItemCorrecao:
    item = ItemCorrecao(
        empresa_id=empresa_id,
        tipo="estoque",
        alvo_chave=alvo_chave,
        campo=campo,
        valor_no_pedido="0",
        valor_sugerido=valor_sugerido,
        justificativa="justificativa de teste",
        fonte="fonte de teste",
        status=status,
        created_at=datetime.now(UTC),
    )
    session.add(item)
    session.flush()
    return item


def _estoque(session: Session, empresa_id: UUID, minimo: int = 0) -> None:
    StockRepository(session).upsert(empresa_id, "SKU-1", "Caixa", 1, minimo, "A1")
    session.commit()


@pytest.mark.parametrize("justificativa", ["", "   ", "\n\t"])
def test_rejeitar_exige_justificativa(db_session: Session, justificativa: str) -> None:
    empresa_id, _ = _empresas(db_session)
    item = _item(db_session, empresa_id)
    db_session.commit()

    with pytest.raises(JustificativaObrigatoria):
        CorrectionService(db_session, empresa_id).rejeitar(
            item.id, uuid4(), "gestor", justificativa
        )

    assert (
        CorrectionRepository(db_session).get(empresa_id, item.id).status == "pendente"
    )
    assert AuditRepository(db_session).list(empresa_id) == []


def test_rejeitar_grava_estado_e_auditoria(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    item = _item(db_session, empresa_id)
    db_session.commit()
    user_id = uuid4()

    rejeitado = CorrectionService(db_session, empresa_id).rejeitar(
        item.id, user_id, "gestor", "  valor incorreto  "
    )

    assert rejeitado.status == "rejeitado"
    assert rejeitado.motivo_rejeicao == "valor incorreto"
    assert rejeitado.decidido_por == user_id
    assert rejeitado.papel_aprovador == "gestor"
    assert rejeitado.decidido_em is not None
    eventos = AuditRepository(db_session).list(empresa_id)
    assert [evento.evento for evento in eventos] == [EVENTO_CORRECAO_REJEITADA]
    assert eventos[0].user_id == user_id


def test_rejeitar_item_inexistente_e_404(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)

    with pytest.raises(CorrecaoNaoEncontrada):
        CorrectionService(db_session, empresa_id).rejeitar(
            uuid4(), uuid4(), "admin", "motivo"
        )


def test_rejeitar_isola_por_empresa(db_session: Session) -> None:
    t1, t2 = _empresas(db_session)
    item = _item(db_session, t1)
    db_session.commit()

    with pytest.raises(CorrecaoNaoEncontrada):
        CorrectionService(db_session, t2).rejeitar(item.id, uuid4(), "admin", "motivo")


@pytest.mark.parametrize("status", ["rejeitado", "aplicado", "falhou"])
def test_rejeitar_item_terminal_recusa(db_session: Session, status: str) -> None:
    empresa_id, _ = _empresas(db_session)
    item = _item(db_session, empresa_id, status=status)
    db_session.commit()

    with pytest.raises(CorrecaoNaoAprovavel):
        CorrectionService(db_session, empresa_id).rejeitar(
            item.id, uuid4(), "gestor", "motivo"
        )

    recarregado = CorrectionRepository(db_session).get(empresa_id, item.id)
    assert recarregado.status == status
    assert recarregado.motivo_rejeicao is None


def test_rejeitar_sem_sugestao_permite(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    item = _item(db_session, empresa_id, valor_sugerido=None)
    db_session.commit()

    rejeitado = CorrectionService(db_session, empresa_id).rejeitar(
        item.id, uuid4(), "gestor", "sem base para aprovar"
    )

    assert rejeitado.status == "rejeitado"
    assert rejeitado.motivo_rejeicao == "sem base para aprovar"


def test_rejeitar_remove_item_da_fila(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    item = _item(db_session, empresa_id)
    db_session.commit()
    servico = CorrectionService(db_session, empresa_id)

    servico.rejeitar(item.id, uuid4(), "gestor", "motivo")

    assert item.id not in {pendente.id for pendente in servico.listar()}


def test_rejeitar_nao_escreve_no_catalogo(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    _estoque(db_session, empresa_id, minimo=0)
    item = _item(db_session, empresa_id)
    db_session.commit()

    CorrectionService(db_session, empresa_id).rejeitar(item.id, uuid4(), "gestor", "x")

    assert StockRepository(db_session).get_by_sku(empresa_id, "SKU-1").minimo == 0
    eventos = {evento.evento for evento in AuditRepository(db_session).list(empresa_id)}
    assert eventos == {EVENTO_CORRECAO_REJEITADA}
