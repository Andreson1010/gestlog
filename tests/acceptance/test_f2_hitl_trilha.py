"""Aceitação F2 (HITL): trilha (TRA) e casos-limite (EDG)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from f2_suporte import (
    HISTORICO,
    aprovar_http,
    campos_pendentes,
    criar_conta,
    criar_empresa,
    definir_decidido_em,
    eventos_auditoria,
    gerar_fila,
    item_correcao,
    ler_estoque,
    login,
    semear_estoque,
    sessao,
)
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session, sessionmaker

from gestlog.audit import purgar_expiradas
from gestlog.correcoes import CorrecaoNaoAprovavel, CorrectionService
from gestlog.correcoes.servico import MOTIVO_CONFLITO
from gestlog.db.models import Empresa, ItemCorrecao, StockItem
from gestlog.repositories.catalog import StockRepository


async def test_tra_01_historico_lista_acoes_com_autor(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    semear_estoque(fabrica_sync, empresa_id, "S2", local="")
    await login(client, "a@tenant.com")
    await aprovar_http(client, fabrica_sync, empresa_id, "S1", "local")
    await aprovar_http(client, fabrica_sync, empresa_id, "S2", "local")

    historico = await client.get(HISTORICO)

    assert historico.status_code == 200
    assert "S1" in historico.text
    assert "S2" in historico.text
    assert "a@tenant.com" in historico.text
    assert 'name="desde"' in historico.text


async def test_tra_02_filtra_periodo_e_mantem_tenant(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    dados_b = await criar_conta(client, "B", "b@tenant.com")
    empresa_b = UUID(dados_b["empresa_id"])
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    semear_estoque(fabrica_sync, empresa_id, "S2", local="")
    semear_estoque(fabrica_sync, empresa_b, "BASE", local="Z9")
    semear_estoque(fabrica_sync, empresa_b, "B1", local="")
    await login(client, "a@tenant.com")
    id_s1 = await aprovar_http(client, fabrica_sync, empresa_id, "S1", "local")
    id_s2 = await aprovar_http(client, fabrica_sync, empresa_id, "S2", "local")
    definir_decidido_em(fabrica_sync, id_s1, datetime(2026, 1, 10, 12, tzinfo=UTC))
    definir_decidido_em(fabrica_sync, id_s2, datetime(2026, 6, 10, 12, tzinfo=UTC))
    gerar_fila(fabrica_sync, empresa_b)
    item_b = item_correcao(fabrica_sync, empresa_b, "B1", "local")
    with sessao(fabrica_sync) as session:
        CorrectionService(session, empresa_b).aprovar(item_b.id, uuid4(), "admin")
    definir_decidido_em(fabrica_sync, item_b.id, datetime(2026, 6, 10, 12, tzinfo=UTC))

    historico = await client.get(
        HISTORICO, params={"desde": "2026-06-01", "ate": "2026-06-30"}
    )

    assert "S2" in historico.text
    assert "S1" not in historico.text
    assert "B1" not in historico.text


async def test_tra_03_historico_vazio_mostra_estado(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    await login(client, "a@tenant.com")
    await aprovar_http(client, fabrica_sync, empresa_id, "S1", "local")

    historico = await client.get(
        HISTORICO, params={"desde": "2000-01-01", "ate": "2000-12-31"}
    )

    assert "Nenhuma correção aplicada no período" in historico.text


async def test_edg_01_cada_campo_tem_item_e_decisao_propria(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", nome="", minimo=0, local="")
    await login(client, "a@tenant.com")
    await client.get("/correcoes")

    assert campos_pendentes(fabrica_sync, empresa_id, "S1") == {
        "nome",
        "minimo",
        "local",
    }

    await aprovar_http(client, fabrica_sync, empresa_id, "S1", "local")

    assert campos_pendentes(fabrica_sync, empresa_id, "S1") == {"nome", "minimo"}


async def test_edg_02_conflito_por_reimportacao_nao_sobrescreve(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    await login(client, "a@tenant.com")
    await client.get("/correcoes")
    item = item_correcao(fabrica_sync, empresa_id, "S1", "local")

    semear_estoque(fabrica_sync, empresa_id, "S1", local="J9")
    resposta = await client.post(
        f"/correcoes/{item.id}/decisao", data={"decisao": "aprovar"}
    )

    assert resposta.status_code == 409
    assert ler_estoque(fabrica_sync, empresa_id, "S1").local == "J9"
    assert (
        item_correcao(
            fabrica_sync, empresa_id, "S1", "local", status="falhou"
        ).motivo_falha
        == MOTIVO_CONFLITO
    )


async def test_edg_03_alvo_removido_encerra_sem_escrita(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    await login(client, "a@tenant.com")
    await client.get("/correcoes")
    item = item_correcao(fabrica_sync, empresa_id, "S1", "local")
    with sessao(fabrica_sync) as session:
        alvo = session.execute(
            select(StockItem).where(
                StockItem.empresa_id == empresa_id, StockItem.sku == "S1"
            )
        ).scalar_one()
        session.delete(alvo)
        session.commit()

    resposta = await client.post(
        f"/correcoes/{item.id}/decisao", data={"decisao": "aprovar"}
    )

    assert resposta.status_code == 409
    falhou = item_correcao(fabrica_sync, empresa_id, "S1", "local", status="falhou")
    assert "inexistente" in (falhou.motivo_falha or "")


async def test_edg_04_decisao_paralela_so_uma_prevalece(
    fabrica_sync: sessionmaker[Session],
) -> None:
    empresa_id = criar_empresa(fabrica_sync)
    usuario_id = uuid4()
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    gerar_fila(fabrica_sync, empresa_id)
    item = item_correcao(fabrica_sync, empresa_id, "S1", "local")
    with sessao(fabrica_sync) as session:
        CorrectionService(session, empresa_id).aprovar(item.id, usuario_id, "admin")

    with sessao(fabrica_sync) as session, pytest.raises(CorrecaoNaoAprovavel):
        CorrectionService(session, empresa_id).aprovar(item.id, usuario_id, "admin")

    with sessao(fabrica_sync) as session:
        assert len(CorrectionService(session, empresa_id).listar("aplicado")) == 1


async def test_edg_05_sugestao_igual_ao_atual_sem_escrita(
    fabrica_sync: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empresa_id = criar_empresa(fabrica_sync)
    semear_estoque(fabrica_sync, empresa_id, "S1", local="A1")
    with sessao(fabrica_sync) as session:
        session.add(
            ItemCorrecao(
                empresa_id=empresa_id,
                tipo="estoque",
                alvo_chave="S1",
                campo="local",
                valor_no_pedido="A1",
                valor_sugerido="A1",
                justificativa="sem mudança",
                fonte="fonte",
                status="pendente",
            )
        )
        session.commit()
    item = item_correcao(fabrica_sync, empresa_id, "S1", "local")
    chamadas: list[object] = []
    monkeypatch.setattr(
        StockRepository, "upsert", lambda *args, **kwargs: chamadas.append(args)
    )

    with sessao(fabrica_sync) as session:
        aprovado = CorrectionService(session, empresa_id).aprovar(
            item.id, uuid4(), "admin"
        )

    assert chamadas == []
    assert aprovado.status == "aplicado"


async def test_edg_06_sem_dados_orienta_importar(client: AsyncClient) -> None:
    await criar_conta(client, "A", "a@tenant.com")
    await login(client, "a@tenant.com")

    pagina = await client.get("/correcoes")

    assert "Sem dados importados" in pagina.text
    assert 'href="/importar"' in pagina.text


async def test_edg_07_fila_vazia_apos_decisoes(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    await login(client, "a@tenant.com")
    await aprovar_http(client, fabrica_sync, empresa_id, "S1", "local")

    pagina = await client.get("/correcoes")

    assert "Nenhuma correção pendente" in pagina.text


async def test_edg_08_limite_mantem_listagem_utilizavel(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    for indice in range(1, 4):
        semear_estoque(fabrica_sync, empresa_id, f"S{indice}", local="")
    await login(client, "a@tenant.com")

    completo = await client.get("/correcoes", params={"limite": 3})
    limitado = await client.get("/correcoes", params={"limite": 1})

    assert completo.text.count('aria-label="Aprovar') == 3
    assert limitado.text.count('aria-label="Aprovar') == 1


async def test_edg_09_sem_sessao_nao_aplica_decisao(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    empresa_id = criar_empresa(fabrica_sync)
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    gerar_fila(fabrica_sync, empresa_id)
    item = item_correcao(fabrica_sync, empresa_id, "S1", "local")

    resposta = await client.post(
        f"/correcoes/{item.id}/decisao", data={"decisao": "aprovar"}
    )

    assert resposta.status_code == 401
    assert item_correcao(fabrica_sync, empresa_id, "S1", "local").status == "pendente"


async def test_edg_10_retencao_purga_decididos_e_preserva_auditoria(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    with sessao(fabrica_sync) as session:
        empresa = session.get(Empresa, empresa_id)
        assert empresa is not None
        empresa.retention_days = 30
        session.commit()
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    semear_estoque(fabrica_sync, empresa_id, "S2", local="")
    await login(client, "a@tenant.com")
    aplicado_id = await aprovar_http(client, fabrica_sync, empresa_id, "S1", "local")
    await client.get("/correcoes")
    pendente = item_correcao(fabrica_sync, empresa_id, "S2", "local")
    antigo = datetime.now(UTC) - timedelta(days=60)
    with sessao(fabrica_sync) as session:
        for item_id in (aplicado_id, pendente.id):
            item = session.get(ItemCorrecao, item_id)
            assert item is not None
            item.created_at = antigo
        session.commit()
    antes = len(eventos_auditoria(fabrica_sync, empresa_id))

    with sessao(fabrica_sync) as session:
        removidas = purgar_expiradas(session)

    assert removidas == 1
    with pytest.raises(NoResultFound):
        item_correcao(fabrica_sync, empresa_id, "S1", "local", status="aplicado")
    assert item_correcao(fabrica_sync, empresa_id, "S2", "local").status == "pendente"
    assert len(eventos_auditoria(fabrica_sync, empresa_id)) == antes
