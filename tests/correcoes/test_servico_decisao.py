"""Testes de integração da aprovação/aplicação de correções (T7)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from gestlog.audit import (
    EVENTO_CORRECAO_APLICADA,
    EVENTO_CORRECAO_APROVADA,
    EVENTO_CORRECAO_FALHOU,
)
from gestlog.correcoes.erros import (
    CorrecaoAlvoInvalido,
    CorrecaoFalhaEscrita,
    CorrecaoNaoAprovavel,
    CorrecaoNaoEncontrada,
)
from gestlog.correcoes.servico import (
    MOTIVO_ALVO_AUSENTE,
    MOTIVO_CONFLITO,
    MOTIVO_ERRO_ESCRITA,
    CorrectionService,
    _valor_auditavel,
)
from gestlog.db.models import ItemCorrecao
from gestlog.repositories.catalog import (
    StockRepository,
    SupplierRepository,
    TransportRepository,
)
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
    tipo: str = "estoque",
    alvo_chave: str = "SKU-1",
    campo: str = "minimo",
    valor_no_pedido: str = "0",
    valor_sugerido: str | None = "9",
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
        created_at=datetime.now(UTC),
    )
    session.add(item)
    session.flush()
    return item


def _estoque(session: Session, empresa_id: UUID, sku: str, **campos: object) -> None:
    base = {
        "nome": "Caixa",
        "quantidade": 1,
        "minimo": 0,
        "local": "A1",
    }
    base.update(campos)
    StockRepository(session).upsert(empresa_id, sku, **base)
    session.commit()


def test_aprovar_aplica_valor_e_audita(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    _estoque(db_session, empresa_id, "SKU-1", minimo=0)
    _estoque(db_session, empresa_id, "SKU-2", minimo=9)
    item = CorrectionService(db_session, empresa_id).gerar_fila()
    alvo = next(i for i in item if i.campo == "minimo")
    assert alvo.valor_sugerido == "9"
    user_id = uuid4()

    aprovado = CorrectionService(db_session, empresa_id).aprovar(
        alvo.id, user_id, "gestor"
    )

    assert aprovado.status == "aplicado"
    assert aprovado.aplicado_em is not None
    assert aprovado.decidido_por == user_id
    assert aprovado.papel_aprovador == "gestor"
    assert StockRepository(db_session).get_by_sku(empresa_id, "SKU-1").minimo == 9
    eventos = AuditRepository(db_session).list(empresa_id)
    assert {e.evento for e in eventos} == {
        EVENTO_CORRECAO_APROVADA,
        EVENTO_CORRECAO_APLICADA,
    }
    assert all(e.user_id == user_id for e in eventos)
    aplicada = next(e for e in eventos if e.evento == EVENTO_CORRECAO_APLICADA)
    assert aplicada.detalhe == {
        "item_id": str(alvo.id),
        "tipo": "estoque",
        "alvo_chave": "SKU-1",
        "campo": "minimo",
        "valor": "9",
    }
    assert not any(
        {"justificativa", "motivo_rejeicao"} & set(e.detalhe or {}) for e in eventos
    )


def test_aprovar_item_inexistente_e_404(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)

    with pytest.raises(CorrecaoNaoEncontrada):
        CorrectionService(db_session, empresa_id).aprovar(uuid4(), uuid4(), "admin")


def test_aprovar_isola_por_empresa(db_session: Session) -> None:
    t1, t2 = _empresas(db_session)
    item = _item(db_session, t1)
    db_session.commit()

    with pytest.raises(CorrecaoNaoEncontrada):
        CorrectionService(db_session, t2).aprovar(item.id, uuid4(), "admin")


def test_aprovar_item_terminal_recusa(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    _estoque(db_session, empresa_id, "SKU-1", minimo=0)
    item = _item(db_session, empresa_id, status="aplicado")
    db_session.commit()

    with pytest.raises(CorrecaoNaoAprovavel):
        CorrectionService(db_session, empresa_id).aprovar(item.id, uuid4(), "gestor")

    assert (
        CorrectionRepository(db_session).get(empresa_id, item.id).status == "aplicado"
    )


def test_aprovar_sem_sugestao_recusa(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    _estoque(db_session, empresa_id, "SKU-1", minimo=0)
    item = _item(db_session, empresa_id, valor_sugerido=None)
    db_session.commit()

    with pytest.raises(CorrecaoNaoAprovavel):
        CorrectionService(db_session, empresa_id).aprovar(item.id, uuid4(), "gestor")

    assert (
        CorrectionRepository(db_session).get(empresa_id, item.id).status == "pendente"
    )


def test_aprovar_alvo_ausente_marca_falhou(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    item = _item(db_session, empresa_id, alvo_chave="SKU-9")
    db_session.commit()

    with pytest.raises(CorrecaoAlvoInvalido):
        CorrectionService(db_session, empresa_id).aprovar(item.id, uuid4(), "gestor")

    recarregado = CorrectionRepository(db_session).get(empresa_id, item.id)
    assert recarregado.status == "falhou"
    assert recarregado.motivo_falha == MOTIVO_ALVO_AUSENTE
    eventos = AuditRepository(db_session).list(empresa_id)
    assert [e.evento for e in eventos] == [EVENTO_CORRECAO_FALHOU]


def test_aprovar_conflito_marca_falhou_sem_sobrescrever(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    _estoque(db_session, empresa_id, "SKU-1", minimo=0)
    item = _item(db_session, empresa_id, valor_no_pedido="0", valor_sugerido="9")
    StockRepository(db_session).upsert(empresa_id, "SKU-1", "Caixa", 1, 5, "A1")
    db_session.commit()

    with pytest.raises(CorrecaoAlvoInvalido):
        CorrectionService(db_session, empresa_id).aprovar(item.id, uuid4(), "gestor")

    recarregado = CorrectionRepository(db_session).get(empresa_id, item.id)
    assert recarregado.status == "falhou"
    assert recarregado.motivo_falha == MOTIVO_CONFLITO
    assert StockRepository(db_session).get_by_sku(empresa_id, "SKU-1").minimo == 5


def test_aprovar_no_op_quando_sugestao_igual_atual(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    empresa_id, _ = _empresas(db_session)
    _estoque(db_session, empresa_id, "SKU-1", minimo=0)
    item = _item(db_session, empresa_id, valor_no_pedido="0", valor_sugerido="0")
    db_session.commit()
    chamadas: list[object] = []
    monkeypatch.setattr(StockRepository, "upsert", lambda *args: chamadas.append(args))

    aprovado = CorrectionService(db_session, empresa_id).aprovar(
        item.id, uuid4(), "gestor"
    )

    assert chamadas == []
    assert aprovado.status == "aplicado"
    eventos = AuditRepository(db_session).list(empresa_id)
    assert {e.evento for e in eventos} == {
        EVENTO_CORRECAO_APROVADA,
        EVENTO_CORRECAO_APLICADA,
    }


def test_aprovar_erro_de_escrita_marca_falhou(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    empresa_id, _ = _empresas(db_session)
    _estoque(db_session, empresa_id, "SKU-1", minimo=0)
    item = _item(db_session, empresa_id, valor_no_pedido="0", valor_sugerido="9")
    db_session.commit()

    def falhar(*args: object, **kwargs: object) -> None:
        raise RuntimeError("falha simulada de escrita")

    monkeypatch.setattr(StockRepository, "upsert", falhar)

    with pytest.raises(CorrecaoFalhaEscrita):
        CorrectionService(db_session, empresa_id).aprovar(item.id, uuid4(), "gestor")

    recarregado = CorrectionRepository(db_session).get(empresa_id, item.id)
    assert recarregado.status == "falhou"
    assert recarregado.motivo_falha == MOTIVO_ERRO_ESCRITA
    assert StockRepository(db_session).get_by_sku(empresa_id, "SKU-1").minimo == 0
    eventos = AuditRepository(db_session).list(empresa_id)
    assert [e.evento for e in eventos] == [EVENTO_CORRECAO_FALHOU]


def test_aprovar_remove_item_da_fila(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    _estoque(db_session, empresa_id, "SKU-1", minimo=0)
    _estoque(db_session, empresa_id, "SKU-2", minimo=9)
    servico = CorrectionService(db_session, empresa_id)
    alvo = next(i for i in servico.gerar_fila() if i.campo == "minimo")

    servico.aprovar(alvo.id, uuid4(), "gestor")

    assert alvo.id not in {item.id for item in servico.listar()}


def test_aprovar_aplica_fornecedor(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    fornecedores = SupplierRepository(db_session)
    fornecedores.upsert(empresa_id, "F-1", "Fornecedor", "", 7, 4.5, True)
    fornecedores.upsert(empresa_id, "F-2", "Outro", "Insumos", 5, 4.0, True)
    db_session.commit()
    servico = CorrectionService(db_session, empresa_id)
    alvo = next(item for item in servico.gerar_fila() if item.campo == "categoria")
    assert alvo.valor_sugerido == "Insumos"

    servico.aprovar(alvo.id, uuid4(), "gestor")

    atualizado = SupplierRepository(db_session).get_by_fornecedor_id(empresa_id, "F-1")
    assert atualizado.categoria == "Insumos"


def test_aprovar_aplica_transporte(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    transportes = TransportRepository(db_session)
    transportes.upsert(empresa_id, "GL-1", "", "Destino", 10.0, "Em trânsito")
    transportes.upsert(empresa_id, "GL-2", "Origem B", "Destino", 1.0, "Entregue")
    db_session.commit()
    servico = CorrectionService(db_session, empresa_id)
    alvo = next(item for item in servico.gerar_fila() if item.campo == "origem")
    assert alvo.valor_sugerido == "Origem B"

    servico.aprovar(alvo.id, uuid4(), "gestor")

    atualizado = TransportRepository(db_session).get_by_codigo(empresa_id, "GL-1")
    assert atualizado.origem == "Origem B"


def test_valor_de_auditoria_e_truncado() -> None:
    assert _valor_auditavel(None) is None
    assert _valor_auditavel("curto") == "curto"
    assert _valor_auditavel("x" * 300) == "x" * 255
