"""Testes de integração do serviço de fila de correções (T5)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from gestlog.correcoes.completude import _CAMPOS
from gestlog.correcoes.servico import _FONTES_CADASTRO, CorrectionService
from gestlog.db.models import ItemCorrecao, StockItem
from gestlog.repositories.catalog import (
    StockRepository,
    SupplierRepository,
    TransportRepository,
)
from gestlog.repositories.correcoes import CorrectionRepository
from gestlog.repositories.empresas import EmpresaRepository


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
    campo: str = "local",
    valor_no_pedido: str = "",
) -> ItemCorrecao:
    item = ItemCorrecao(
        empresa_id=empresa_id,
        tipo=tipo,
        alvo_chave=alvo_chave,
        campo=campo,
        valor_no_pedido=valor_no_pedido,
        valor_sugerido=None,
        justificativa="justificativa de teste",
        fonte="fonte de teste",
        status=status,
        created_at=datetime.now(UTC),
    )
    session.add(item)
    session.flush()
    return item


def test_mapa_de_fontes_cobre_tipos_e_chaves_da_completude() -> None:
    assert set(_FONTES_CADASTRO) == set(_CAMPOS)
    for fabrica, chave, metodo in _FONTES_CADASTRO.values():
        assert chave in fabrica.model.__mapper__.columns
        assert callable(getattr(fabrica, metodo))


def test_gerar_fila_materializa_um_item_por_campo_faltante(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    StockRepository(db_session).upsert(empresa_id, "SKU-1", "", 0, 0, "")
    db_session.commit()

    criados = CorrectionService(db_session, empresa_id).gerar_fila()

    assert {item.campo for item in criados} == {"nome", "minimo", "local"}
    assert all(item.status == "pendente" for item in criados)
    assert all(item.alvo_chave == "SKU-1" for item in criados)
    assert all(item.tipo == "estoque" for item in criados)


def test_gerar_fila_e_idempotente(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    StockRepository(db_session).upsert(empresa_id, "SKU-1", "", 0, 0, "")
    db_session.commit()
    servico = CorrectionService(db_session, empresa_id)

    primeira = servico.gerar_fila()
    segunda = servico.gerar_fila()

    assert len(primeira) == 3
    assert segunda == []
    pendentes = CorrectionRepository(db_session).list_by_status(empresa_id, "pendente")
    assert len(pendentes) == 3


def test_gerar_fila_sem_dados_e_vazia(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)

    assert CorrectionService(db_session, empresa_id).gerar_fila() == []
    assert CorrectionRepository(db_session).list(empresa_id) == []


def test_gerar_fila_ignora_registro_completo(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    StockRepository(db_session).upsert(empresa_id, "SKU-1", "Caixa", 10, 5, "A1")
    db_session.commit()

    assert CorrectionService(db_session, empresa_id).gerar_fila() == []


def test_gerar_fila_cobre_os_tres_tipos(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    StockRepository(db_session).upsert(empresa_id, "SKU-1", "", 0, 0, "")
    SupplierRepository(db_session).upsert(empresa_id, "F-1", "", "", 0, 0.0, True)
    TransportRepository(db_session).upsert(empresa_id, "GL-1", "", "", 0.0, "")
    db_session.commit()

    criados = CorrectionService(db_session, empresa_id).gerar_fila()

    assert {item.tipo for item in criados} == {"estoque", "fornecedores", "transporte"}


def test_gerar_fila_usa_sugestao_e_marca_sem_base(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    fornecedores = SupplierRepository(db_session)
    fornecedores.upsert(empresa_id, "F-1", "Fornecedor", "", 7, 4.5, True)
    fornecedores.upsert(empresa_id, "F-2", "Outro", "Insumos", 5, 4.0, True)
    fornecedores.upsert(empresa_id, "F-3", "Terceiro", "Insumos", 9, 5.0, True)
    StockRepository(db_session).upsert(empresa_id, "SKU-1", "", 0, 5, "A1")
    db_session.commit()

    criados = CorrectionService(db_session, empresa_id).gerar_fila()
    por_chave = {(item.tipo, item.campo): item for item in criados}

    categoria = por_chave[("fornecedores", "categoria")]
    assert categoria.valor_sugerido == "Insumos"
    assert categoria.fonte == "categoria mais comum entre 2 fornecedores"
    nome_estoque = por_chave[("estoque", "nome")]
    assert nome_estoque.valor_sugerido is None
    assert nome_estoque.justificativa == "sem base de dados no tenant"


def test_gerar_fila_nao_recria_item_terminal_com_mesmo_valor(
    db_session: Session,
) -> None:
    empresa_id, _ = _empresas(db_session)
    _item(db_session, empresa_id, status="rejeitado", campo="local", valor_no_pedido="")
    StockRepository(db_session).upsert(empresa_id, "SKU-1", "", 0, 0, "")
    db_session.commit()

    criados = CorrectionService(db_session, empresa_id).gerar_fila()

    assert {item.campo for item in criados} == {"nome", "minimo"}


def test_gerar_fila_cria_novo_quando_valor_muda(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    _item(db_session, empresa_id, status="rejeitado", campo="local", valor_no_pedido="")
    StockRepository(db_session).upsert(empresa_id, "SKU-1", "Caixa", 5, 5, "  ")
    db_session.commit()

    criados = CorrectionService(db_session, empresa_id).gerar_fila()

    assert [item.campo for item in criados] == ["local"]
    assert criados[0].valor_no_pedido == "  "


def test_gerar_fila_nao_duplica_item_aberto(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    _item(db_session, empresa_id, status="pendente", campo="local", valor_no_pedido="")
    StockRepository(db_session).upsert(empresa_id, "SKU-1", "Caixa", 5, 5, "  ")
    db_session.commit()

    assert CorrectionService(db_session, empresa_id).gerar_fila() == []


def test_gerar_fila_normaliza_chave_em_maiuscula(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    db_session.add(
        StockItem(empresa_id=empresa_id, sku="sku-9", nome="", quantidade=0, minimo=0)
    )
    db_session.commit()

    criados = CorrectionService(db_session, empresa_id).gerar_fila()

    assert {item.alvo_chave for item in criados} == {"SKU-9"}


def test_gerar_fila_isola_por_empresa(db_session: Session) -> None:
    t1, t2 = _empresas(db_session)
    StockRepository(db_session).upsert(t1, "SKU-1", "", 0, 0, "")
    db_session.commit()

    assert CorrectionService(db_session, t2).gerar_fila() == []
    assert CorrectionRepository(db_session).list(t2) == []
    assert len(CorrectionService(db_session, t1).gerar_fila()) == 3


def test_listar_filtra_status_e_limita(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    _item(db_session, empresa_id, status="pendente", alvo_chave="SKU-1")
    _item(db_session, empresa_id, status="pendente", alvo_chave="SKU-2")
    _item(db_session, empresa_id, status="aplicado", alvo_chave="SKU-3")
    db_session.commit()
    servico = CorrectionService(db_session, empresa_id)

    assert len(servico.listar()) == 2
    assert [item.alvo_chave for item in servico.listar("aplicado")] == ["SKU-3"]
    assert len(servico.listar(limite=1)) == 1
