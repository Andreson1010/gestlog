"""Aceitação F2 (HITL): decidir na fila (APR) e aplicar/auditar (ESC)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from f2_suporte import (
    aprovar_http,
    convidar,
    criar_conta,
    criar_empresa,
    eventos_auditoria,
    gerar_fila,
    item_correcao,
    ler_estoque,
    login,
    semear_estoque,
    sessao,
)
from httpx import AsyncClient
from sqlalchemy.orm import Session, sessionmaker

from gestlog.correcoes import (
    CorrecaoAlvoInvalido,
    CorrecaoFalhaEscrita,
    CorrectionService,
)
from gestlog.correcoes.servico import MOTIVO_ERRO_ESCRITA
from gestlog.db.models import ItemCorrecao
from gestlog.repositories.catalog import StockRepository


async def test_apr_01_sugestao_pendente_acionavel(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    await login(client, "a@tenant.com")

    pagina = await client.get("/correcoes")

    assert 'aria-label="Aprovar local de S1"' in pagina.text
    assert 'action="/correcoes/' in pagina.text


async def test_apr_02_aprovar_registra_decisao(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    usuario_id = UUID(dados["usuario_id"])
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    await login(client, "a@tenant.com")

    await aprovar_http(client, fabrica_sync, empresa_id, "S1", "local")

    item = item_correcao(fabrica_sync, empresa_id, "S1", "local", status="aplicado")
    assert item.decidido_por == usuario_id
    assert item.papel_aprovador == "admin"
    assert item.decidido_em is not None
    assert item.aplicado_em is not None


async def test_apr_03_rejeitar_exige_e_registra_justificativa(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    usuario_id = UUID(dados["usuario_id"])
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    await login(client, "a@tenant.com")
    await client.get("/correcoes")
    item = item_correcao(fabrica_sync, empresa_id, "S1", "local")

    sem_motivo = await client.post(
        f"/correcoes/{item.id}/decisao",
        data={"decisao": "rejeitar", "justificativa": "   "},
    )
    assert sem_motivo.status_code == 422

    com_motivo = await client.post(
        f"/correcoes/{item.id}/decisao",
        data={"decisao": "rejeitar", "justificativa": "local incorreto"},
        follow_redirects=False,
    )
    assert com_motivo.status_code == 303

    rejeitado = item_correcao(
        fabrica_sync, empresa_id, "S1", "local", status="rejeitado"
    )
    assert rejeitado.motivo_rejeicao == "local incorreto"
    assert rejeitado.decidido_por == usuario_id
    assert rejeitado.papel_aprovador == "admin"
    assert rejeitado.decidido_em is not None


async def test_apr_04_operador_sem_papel_e_negado(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    await login(client, "a@tenant.com")
    await convidar(client, "op@tenant.com")
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    gerar_fila(fabrica_sync, empresa_id)
    item = item_correcao(fabrica_sync, empresa_id, "S1", "local")

    await login(client, "op@tenant.com")

    assert (await client.get("/correcoes")).status_code == 403
    negado = await client.post(
        f"/correcoes/{item.id}/decisao", data={"decisao": "aprovar"}
    )
    assert negado.status_code == 403
    assert item_correcao(fabrica_sync, empresa_id, "S1", "local").status == "pendente"


async def test_apr_05_item_terminal_recusa_nova_decisao(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    await login(client, "a@tenant.com")
    item_id = await aprovar_http(client, fabrica_sync, empresa_id, "S1", "local")

    resposta = await client.post(
        f"/correcoes/{item_id}/decisao", data={"decisao": "aprovar"}
    )

    assert resposta.status_code == 409
    terminal = item_correcao(fabrica_sync, empresa_id, "S1", "local", status="aplicado")
    assert terminal.decidido_por is not None


async def test_apr_06_item_de_outro_tenant_recebe_404(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    await criar_conta(client, "A", "a@tenant.com")
    dados_b = await criar_conta(client, "B", "b@tenant.com")
    empresa_b = UUID(dados_b["empresa_id"])
    semear_estoque(fabrica_sync, empresa_b, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_b, "B1", local="")
    gerar_fila(fabrica_sync, empresa_b)
    item_b = item_correcao(fabrica_sync, empresa_b, "B1", "local")

    await login(client, "a@tenant.com")
    resposta = await client.post(
        f"/correcoes/{item_b.id}/decisao", data={"decisao": "aprovar"}
    )

    assert resposta.status_code == 404


async def test_esc_01_aprovar_aplica_ao_alvo(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", nome="Parafuso", minimo=3)
    await login(client, "a@tenant.com")

    await aprovar_http(client, fabrica_sync, empresa_id, "S1", "local")

    corrigido = ler_estoque(fabrica_sync, empresa_id, "S1")
    assert corrigido.local == "A1"
    assert corrigido.nome == "Parafuso"
    assert corrigido.minimo == 3


async def test_esc_02_auditoria_com_autor_e_metadados(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    usuario_id = UUID(dados["usuario_id"])
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    await login(client, "a@tenant.com")

    await aprovar_http(client, fabrica_sync, empresa_id, "S1", "local")

    eventos = {
        evento.evento: evento for evento in eventos_auditoria(fabrica_sync, empresa_id)
    }
    assert set(eventos) == {"correcao_aprovada", "correcao_aplicada"}
    aplicada = eventos["correcao_aplicada"]
    assert aplicada.user_id == usuario_id
    assert aplicada.created_at is not None
    assert aplicada.detalhe["alvo_chave"] == "S1"
    assert aplicada.detalhe["campo"] == "local"
    assert aplicada.detalhe["valor"] == "A1"


async def test_esc_03_item_sai_da_fila_apos_aplicar(
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


async def test_esc_04_falha_de_escrita_preserva_valor(
    fabrica_sync: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empresa_id = criar_empresa(fabrica_sync)
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    gerar_fila(fabrica_sync, empresa_id)
    item = item_correcao(fabrica_sync, empresa_id, "S1", "local")

    def falhar(*args: object, **kwargs: object) -> None:
        raise RuntimeError("falha simulada de escrita")

    monkeypatch.setattr(StockRepository, "upsert", falhar)

    with sessao(fabrica_sync) as session, pytest.raises(CorrecaoFalhaEscrita):
        CorrectionService(session, empresa_id).aprovar(item.id, uuid4(), "admin")

    recarregado = item_correcao(
        fabrica_sync, empresa_id, "S1", "local", status="falhou"
    )
    assert recarregado.motivo_falha == MOTIVO_ERRO_ESCRITA
    assert ler_estoque(fabrica_sync, empresa_id, "S1").local == ""


async def test_esc_05_alvo_de_outro_tenant_recusado_sem_vazar(
    fabrica_sync: sessionmaker[Session],
) -> None:
    empresa_a = criar_empresa(fabrica_sync, "A")
    empresa_b = criar_empresa(fabrica_sync, "B")
    semear_estoque(fabrica_sync, empresa_b, "SHARED", local="ORIGEM")
    with sessao(fabrica_sync) as session:
        session.add(
            ItemCorrecao(
                empresa_id=empresa_a,
                tipo="estoque",
                alvo_chave="SHARED",
                campo="local",
                valor_no_pedido="",
                valor_sugerido="NOVO",
                justificativa="justificativa de teste",
                fonte="fonte de teste",
                status="pendente",
            )
        )
        session.commit()
    item = item_correcao(fabrica_sync, empresa_a, "SHARED", "local")

    with sessao(fabrica_sync) as session, pytest.raises(CorrecaoAlvoInvalido):
        CorrectionService(session, empresa_a).aprovar(item.id, uuid4(), "admin")

    assert ler_estoque(fabrica_sync, empresa_b, "SHARED").local == "ORIGEM"


async def test_esc_06_auditoria_sem_texto_livre_e_truncada(
    fabrica_sync: sessionmaker[Session],
) -> None:
    empresa_id = criar_empresa(fabrica_sync)
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    with sessao(fabrica_sync) as session:
        session.add(
            ItemCorrecao(
                empresa_id=empresa_id,
                tipo="estoque",
                alvo_chave="S1",
                campo="local",
                valor_no_pedido="",
                valor_sugerido="x" * 300,
                justificativa="texto livre que não deve ir à auditoria",
                fonte="fonte",
                status="pendente",
            )
        )
        session.commit()
    item = item_correcao(fabrica_sync, empresa_id, "S1", "local")

    with sessao(fabrica_sync) as session:
        CorrectionService(session, empresa_id).aprovar(item.id, uuid4(), "admin")

    aplicada = next(
        evento
        for evento in eventos_auditoria(fabrica_sync, empresa_id)
        if evento.evento == "correcao_aplicada"
    )
    assert set(aplicada.detalhe) == {
        "item_id",
        "tipo",
        "alvo_chave",
        "campo",
        "valor",
    }
    assert len(aplicada.detalhe["valor"]) == 255
    assert "justificativa" not in aplicada.detalhe
