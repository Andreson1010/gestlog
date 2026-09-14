"""Testes de integração do serviço de importação (T12)."""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from gestlog.ingestion import ArquivoVazio, TipoImportacaoInvalido, historico, importar
from gestlog.repositories.catalog import (
    StockRepository,
    SupplierRepository,
    TransportRepository,
)
from gestlog.repositories.empresas import EmpresaRepository


def _empresas(session: Session) -> tuple[UUID, UUID]:
    repo = EmpresaRepository(session)
    a = repo.create("A")
    b = repo.create("B")
    session.commit()
    return a.id, b.id


def _csv(texto: str) -> bytes:
    return texto.encode("utf-8")


def test_importar_estoque_grava_registros_e_status(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    conteudo = _csv("sku,nome,quantidade,minimo,local\nSKU-1,Caixa,10,2,A1\n")

    job = importar(db_session, empresa_id, "estoque", conteudo, "estoque.csv")
    db_session.commit()

    assert job.status == "concluido"
    assert job.aceitas == 1
    assert job.rejeitadas == 0
    item = StockRepository(db_session).get_by_sku(empresa_id, "SKU-1")
    assert item is not None
    assert item.quantidade == 10


def test_importar_registra_erros_por_linha(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    conteudo = _csv("sku,nome,quantidade,minimo\nSKU-1,Caixa,10,2\n,Caixa,3,1\n")

    job = importar(db_session, empresa_id, "estoque", conteudo)
    db_session.commit()

    assert job.aceitas == 1
    assert job.rejeitadas == 1
    assert len(job.errors) == 1
    assert job.errors[0].linha == 3
    assert "sku" in job.errors[0].motivo


def test_importar_substitui_registro_existente(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)
    StockRepository(db_session).upsert(empresa_id, "SKU-1", "Antigo", 1, 1, "")
    db_session.commit()

    importar(
        db_session,
        empresa_id,
        "estoque",
        _csv("sku,nome,quantidade,minimo\nsku-1,Novo,99,5\n"),
    )
    db_session.commit()

    itens = StockRepository(db_session).list(empresa_id)
    assert len(itens) == 1
    assert itens[0].nome == "Novo"
    assert itens[0].quantidade == 99


def test_importar_fornecedores_e_transporte(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)

    importar(
        db_session,
        empresa_id,
        "fornecedores",
        _csv("fornecedor_id,nome\nF-1,TransLog\n"),
    )
    importar(
        db_session,
        empresa_id,
        "transporte",
        _csv("codigo_rastreio,origem,destino,peso_kg\nGL-1,SP,CWB,10\n"),
    )
    db_session.commit()

    supplier = SupplierRepository(db_session).get_by_fornecedor_id(empresa_id, "F-1")
    registro = TransportRepository(db_session).get_by_codigo(empresa_id, "GL-1")
    assert supplier is not None
    assert registro is not None


def test_historico_isola_por_empresa(db_session: Session) -> None:
    a, b = _empresas(db_session)

    importar(
        db_session, a, "estoque", _csv("sku,nome,quantidade,minimo\nSKU-1,Caixa,1,0\n")
    )
    db_session.commit()

    assert len(historico(db_session, a)) == 1
    assert historico(db_session, b) == []


def test_arquivo_invalido_nao_grava(db_session: Session) -> None:
    empresa_id, _ = _empresas(db_session)

    with pytest.raises(ArquivoVazio):
        importar(db_session, empresa_id, "estoque", b"")
    with pytest.raises(TipoImportacaoInvalido):
        importar(db_session, empresa_id, "inexistente", _csv("a\n1\n"))
    db_session.commit()

    assert historico(db_session, empresa_id) == []
    assert StockRepository(db_session).list(empresa_id) == []
