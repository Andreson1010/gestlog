"""Testes de agregação dos relatórios por domínio (REL-06..REL-18)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from gestlog.db.models import CatalogoHistorico
from gestlog.repositories.relatorios import RelatorioRepository


def _snap(
    session: Session,
    empresa_id: UUID,
    dominio: str,
    chave: str,
    quando: datetime,
    **payload: object,
) -> None:
    session.add(
        CatalogoHistorico(
            empresa_id=empresa_id,
            dominio=dominio,
            chave=chave,
            importado_em=quando,
            **payload,
        )
    )
    session.flush()


def test_estoque_classifica_abaixo_excedente_e_agrega(db_session: Session) -> None:
    empresa = uuid4()
    quando = datetime(2026, 6, 10, 12, tzinfo=UTC)
    _snap(
        db_session,
        empresa,
        "estoque",
        "S1",
        quando,
        nome="A",
        categoria="X",
        local="L1",
        quantidade=1,
        minimo=5,
    )
    _snap(
        db_session,
        empresa,
        "estoque",
        "S2",
        quando,
        nome="B",
        categoria="X",
        local="L1",
        quantidade=30,
        minimo=5,
    )
    _snap(
        db_session,
        empresa,
        "estoque",
        "S3",
        quando,
        nome="C",
        categoria="Y",
        local="L2",
        quantidade=5,
        minimo=5,
    )
    _snap(
        db_session,
        empresa,
        "estoque",
        "S4",
        quando,
        nome="D",
        categoria="Y",
        local="L2",
        quantidade=10,
        minimo=0,
    )
    db_session.commit()

    resumo = RelatorioRepository(db_session).estoque(empresa)

    assert {item.chave for item in resumo.abaixo_minimo} == {"S1"}
    assert {item.chave for item in resumo.excedentes} == {"S2"}
    assert dict(resumo.por_local) == {"L1": 2, "L2": 2}
    assert dict(resumo.por_categoria) == {"X": 2, "Y": 2}


def test_estoque_minimo_zero_nunca_e_excedente(db_session: Session) -> None:
    empresa = uuid4()
    quando = datetime(2026, 6, 10, 12, tzinfo=UTC)
    _snap(
        db_session,
        empresa,
        "estoque",
        "S1",
        quando,
        nome="A",
        local="L1",
        quantidade=100,
        minimo=0,
    )
    db_session.commit()

    resumo = RelatorioRepository(db_session).estoque(empresa)

    assert resumo.excedentes == ()
    assert resumo.itens[0].situacao == "Normal"


def test_estoque_isola_por_empresa(db_session: Session) -> None:
    empresa_a, empresa_b = uuid4(), uuid4()
    quando = datetime(2026, 6, 10, 12, tzinfo=UTC)
    _snap(
        db_session,
        empresa_a,
        "estoque",
        "S1",
        quando,
        nome="A",
        quantidade=1,
        minimo=5,
    )
    _snap(
        db_session,
        empresa_b,
        "estoque",
        "S2",
        quando,
        nome="B",
        quantidade=99,
        minimo=5,
    )
    db_session.commit()

    resumo = RelatorioRepository(db_session).estoque(empresa_a)

    assert [item.chave for item in resumo.itens] == ["S1"]


def test_estoque_ultimo_snapshot_por_chave_vence(db_session: Session) -> None:
    empresa = uuid4()
    dia = datetime(2026, 6, 10, 8, tzinfo=UTC)
    _snap(
        db_session,
        empresa,
        "estoque",
        "S1",
        dia,
        nome="A",
        quantidade=1,
        minimo=5,
    )
    _snap(
        db_session,
        empresa,
        "estoque",
        "S1",
        dia + timedelta(hours=4),
        nome="A",
        quantidade=99,
        minimo=5,
    )
    db_session.commit()

    resumo = RelatorioRepository(db_session).estoque(empresa)

    assert len(resumo.itens) == 1
    assert resumo.itens[0].quantidade == 99


def test_estoque_recorte_de_igual_a_ate_cobre_o_dia(db_session: Session) -> None:
    empresa = uuid4()
    dentro = datetime(2026, 6, 10, 12, tzinfo=UTC)
    fora = datetime(2026, 6, 12, 12, tzinfo=UTC)
    _snap(
        db_session, empresa, "estoque", "S1", dentro, nome="A", quantidade=1, minimo=5
    )
    _snap(db_session, empresa, "estoque", "S2", fora, nome="B", quantidade=1, minimo=5)
    db_session.commit()

    desde = datetime.combine(date(2026, 6, 10), time.min, tzinfo=UTC)
    ate = datetime.combine(date(2026, 6, 10), time.max, tzinfo=UTC)
    resumo = RelatorioRepository(db_session).estoque(empresa, desde, ate)

    assert [item.chave for item in resumo.itens] == ["S1"]


def test_estoque_recorte_apenas_um_limite(db_session: Session) -> None:
    empresa = uuid4()
    janeiro = datetime(2026, 1, 10, 12, tzinfo=UTC)
    junho = datetime(2026, 6, 10, 12, tzinfo=UTC)
    _snap(
        db_session, empresa, "estoque", "S1", janeiro, nome="A", quantidade=1, minimo=5
    )
    _snap(db_session, empresa, "estoque", "S2", junho, nome="B", quantidade=1, minimo=5)
    db_session.commit()

    repo = RelatorioRepository(db_session)
    so_desde = repo.estoque(empresa, desde=datetime(2026, 6, 1, tzinfo=UTC))
    so_ate = repo.estoque(empresa, ate=datetime(2026, 1, 31, tzinfo=UTC))

    assert [item.chave for item in so_desde.itens] == ["S2"]
    assert [item.chave for item in so_ate.itens] == ["S1"]


def test_estoque_dedup_mesma_chave_mesma_importacao(db_session: Session) -> None:
    """Chave repetida na mesma importação vira uma linha e não dobra agregados."""
    empresa = uuid4()
    quando = datetime(2026, 6, 10, 12, tzinfo=UTC)
    _snap(
        db_session,
        empresa,
        "estoque",
        "S1",
        quando,
        id=UUID(int=1),
        nome="A",
        categoria="X",
        local="L1",
        quantidade=1,
        minimo=5,
    )
    _snap(
        db_session,
        empresa,
        "estoque",
        "S1",
        quando,
        id=UUID(int=2),
        nome="A",
        categoria="X",
        local="L1",
        quantidade=2,
        minimo=5,
    )
    db_session.commit()

    resumo = RelatorioRepository(db_session).estoque(empresa)

    assert [item.chave for item in resumo.itens] == ["S1"]
    assert dict(resumo.por_local) == {"L1": 1}
    assert dict(resumo.por_categoria) == {"X": 1}


def test_estoque_dedup_vence_maior_id(db_session: Session) -> None:
    """No empate de importado_em, vence o snapshot de maior id."""
    empresa = uuid4()
    quando = datetime(2026, 6, 10, 12, tzinfo=UTC)
    _snap(
        db_session,
        empresa,
        "estoque",
        "S1",
        quando,
        id=UUID(int=1),
        nome="A",
        quantidade=1,
        minimo=5,
    )
    _snap(
        db_session,
        empresa,
        "estoque",
        "S1",
        quando,
        id=UUID(int=2),
        nome="A",
        quantidade=99,
        minimo=5,
    )
    db_session.commit()

    resumo = RelatorioRepository(db_session).estoque(empresa)

    assert len(resumo.itens) == 1
    assert resumo.itens[0].quantidade == 99


def test_estoque_segundo_import_nao_duplica_chave(db_session: Session) -> None:
    """Um segundo import com a mesma chave mantém uma linha, a mais recente."""
    empresa = uuid4()
    primeiro = datetime(2026, 6, 9, 12, tzinfo=UTC)
    segundo = datetime(2026, 6, 10, 12, tzinfo=UTC)
    _snap(
        db_session,
        empresa,
        "estoque",
        "S1",
        primeiro,
        id=UUID(int=1),
        nome="A",
        quantidade=1,
        minimo=5,
    )
    _snap(
        db_session,
        empresa,
        "estoque",
        "S1",
        segundo,
        id=UUID(int=2),
        nome="A",
        quantidade=2,
        minimo=5,
    )
    _snap(
        db_session,
        empresa,
        "estoque",
        "S1",
        segundo,
        id=UUID(int=3),
        nome="A",
        quantidade=30,
        minimo=5,
    )
    db_session.commit()

    resumo = RelatorioRepository(db_session).estoque(empresa)

    assert [item.chave for item in resumo.itens] == ["S1"]
    assert resumo.itens[0].quantidade == 30
    assert dict(resumo.por_local) == {"": 1}


def test_transporte_dedup_mesma_chave_nao_duplica_agregados(
    db_session: Session,
) -> None:
    """Chave repetida na mesma importação não dobra peso, status nem atrasos."""
    empresa = uuid4()
    quando = datetime(2026, 6, 10, 12, tzinfo=UTC)
    for identificador in (UUID(int=1), UUID(int=2)):
        _snap(
            db_session,
            empresa,
            "transporte",
            "R1",
            quando,
            id=identificador,
            origem="SP",
            destino="CWB",
            peso_kg=10.0,
            status="ok",
            previsao_entrega=datetime(2026, 6, 10, tzinfo=UTC),
            data_entrega=datetime(2026, 6, 15, tzinfo=UTC),
        )
    db_session.commit()

    resumo = RelatorioRepository(db_session).transporte(empresa)

    assert [registro.chave for registro in resumo.registros] == ["R1"]
    assert resumo.atrasos == 1
    assert dict(resumo.por_status) == {"ok": 1}
    assert dict(resumo.peso_por_rota) == {"SP → CWB": 10.0}


def test_transporte_agrega_status_peso_e_atrasos(db_session: Session) -> None:
    empresa = uuid4()
    quando = datetime(2026, 6, 10, 12, tzinfo=UTC)
    _snap(
        db_session,
        empresa,
        "transporte",
        "R1",
        quando,
        origem="SP",
        destino="CWB",
        peso_kg=10.0,
        status="ok",
        previsao_entrega=datetime(2026, 6, 10, tzinfo=UTC),
        data_entrega=datetime(2026, 6, 5, tzinfo=UTC),
    )
    _snap(
        db_session,
        empresa,
        "transporte",
        "R2",
        quando,
        origem="SP",
        destino="CWB",
        peso_kg=5.0,
        status="ok",
        previsao_entrega=datetime(2026, 6, 10, tzinfo=UTC),
        data_entrega=datetime(2026, 6, 15, tzinfo=UTC),
    )
    _snap(
        db_session,
        empresa,
        "transporte",
        "R3",
        quando,
        origem="MG",
        destino="SP",
        peso_kg=0.0,
        status="pendente",
    )
    db_session.commit()

    resumo = RelatorioRepository(db_session).transporte(empresa)

    assert resumo.atrasos == 1
    assert dict(resumo.por_status) == {"ok": 2, "pendente": 1}
    assert dict(resumo.peso_por_rota) == {"SP → CWB": 15.0, "MG → SP": 0.0}


def test_transporte_status_vazio_conta_como_valor_real(db_session: Session) -> None:
    empresa = uuid4()
    quando = datetime(2026, 6, 10, 12, tzinfo=UTC)
    _snap(
        db_session,
        empresa,
        "transporte",
        "R1",
        quando,
        origem="SP",
        destino="CWB",
        peso_kg=1.0,
        status="",
    )
    db_session.commit()

    resumo = RelatorioRepository(db_session).transporte(empresa)

    assert dict(resumo.por_status) == {"": 1}


def test_fornecedores_distribui_e_calcula_medias(db_session: Session) -> None:
    empresa = uuid4()
    quando = datetime(2026, 6, 10, 12, tzinfo=UTC)
    _snap(
        db_session,
        empresa,
        "fornecedores",
        "F1",
        quando,
        nome="A",
        categoria="X",
        prazo_dias=10,
        avaliacao=4.0,
        ativo=True,
    )
    _snap(
        db_session,
        empresa,
        "fornecedores",
        "F2",
        quando,
        nome="B",
        categoria="X",
        prazo_dias=0,
        avaliacao=0.0,
        ativo=True,
    )
    _snap(
        db_session,
        empresa,
        "fornecedores",
        "F3",
        quando,
        nome="C",
        categoria="Y",
        prazo_dias=5,
        avaliacao=5.0,
        ativo=False,
    )
    db_session.commit()

    resumo = RelatorioRepository(db_session).fornecedores(empresa)

    assert resumo.ativos == 2
    assert resumo.inativos == 1
    assert resumo.avaliacao_media == 3.0
    assert resumo.prazo_medio == 5.0
    assert dict(resumo.por_categoria) == {"X": 2, "Y": 1}
    assert {fornecedor.situacao for fornecedor in resumo.fornecedores} == {
        "Ativo",
        "Inativo",
    }


def test_relatorios_vazios_nao_levantam(db_session: Session) -> None:
    empresa = uuid4()
    repo = RelatorioRepository(db_session)

    estoque = repo.estoque(empresa)
    transporte = repo.transporte(empresa)
    fornecedores = repo.fornecedores(empresa)

    assert estoque.itens == ()
    assert estoque.por_local == ()
    assert transporte.registros == ()
    assert transporte.atrasos == 0
    assert fornecedores.fornecedores == ()
    assert fornecedores.avaliacao_media == 0.0
    assert fornecedores.prazo_medio == 0.0
