"""Aceitação F2 (HITL): listar incompletos (INC) e sugerir valores (SUG)."""

from __future__ import annotations

from uuid import UUID

from f2_suporte import (
    criar_conta,
    criar_empresa,
    gerar_fila,
    item_correcao,
    login,
    semear_estoque,
)
from httpx import AsyncClient
from sqlalchemy.orm import Session, sessionmaker


async def test_inc_01_lista_apenas_incompletos_do_tenant(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados_a = await criar_conta(client, "A", "a@tenant.com")
    dados_b = await criar_conta(client, "B", "b@tenant.com")
    semear_estoque(fabrica_sync, UUID(dados_a["empresa_id"]), "S1", local="")
    semear_estoque(fabrica_sync, UUID(dados_b["empresa_id"]), "B1", local="")
    await login(client, "a@tenant.com")

    pagina = await client.get("/correcoes")

    assert pagina.status_code == 200
    assert "S1" in pagina.text
    assert "B1" not in pagina.text
    assert "Correções de estoque" in pagina.text


async def test_inc_02_indica_campos_faltantes(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    semear_estoque(fabrica_sync, UUID(dados["empresa_id"]), "S1", minimo=0, local="")
    await login(client, "a@tenant.com")

    pagina = await client.get("/correcoes")

    assert pagina.status_code == 200
    assert "<td>minimo</td>" in pagina.text
    assert "<td>local</td>" in pagina.text


async def test_inc_03_lista_isola_outro_tenant(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    await criar_conta(client, "A", "a@tenant.com")
    dados_b = await criar_conta(client, "B", "b@tenant.com")
    semear_estoque(fabrica_sync, UUID(dados_b["empresa_id"]), "B1", local="")
    await login(client, "a@tenant.com")

    pagina = await client.get("/correcoes")

    assert pagina.status_code == 200
    assert "B1" not in pagina.text


async def test_inc_04_sem_incompletos_mostra_estado_vazio(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    semear_estoque(fabrica_sync, UUID(dados["empresa_id"]), "OK", local="A1")
    await login(client, "a@tenant.com")

    pagina = await client.get("/correcoes")

    assert pagina.status_code == 200
    assert "Nenhuma correção pendente" in pagina.text


async def test_inc_05_sem_sessao_recebe_401(client: AsyncClient) -> None:
    assert (await client.get("/correcoes")).status_code == 401


async def test_sug_01_sugere_valor_do_proprio_tenant(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    await login(client, "a@tenant.com")

    pagina = await client.get("/correcoes")

    assert "A1" in pagina.text


async def test_sug_02_apresenta_justificativa_e_fonte(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    await login(client, "a@tenant.com")

    pagina = await client.get("/correcoes")

    assert "valor mais frequente" in pagina.text
    assert "local mais comum nos itens" in pagina.text


async def test_sug_03_sem_base_marca_sem_sugestao(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    semear_estoque(fabrica_sync, UUID(dados["empresa_id"]), "S1", local="")
    await login(client, "a@tenant.com")

    pagina = await client.get("/correcoes")

    assert "sem sugestão" in pagina.text
    assert 'aria-label="Aprovar' not in pagina.text


def test_sug_04_sugestao_rastreavel_no_item(
    fabrica_sync: sessionmaker[Session],
) -> None:
    empresa_id = criar_empresa(fabrica_sync)
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    gerar_fila(fabrica_sync, empresa_id)

    item = item_correcao(fabrica_sync, empresa_id, "S1", "local")

    assert item.valor_sugerido == "A1"
    assert item.justificativa
    assert item.fonte == "local mais comum nos itens"


async def test_sug_05_distingue_atual_sugerido_e_origem(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    semear_estoque(fabrica_sync, empresa_id, "BASE", local="A1")
    semear_estoque(fabrica_sync, empresa_id, "S1", local="")
    await login(client, "a@tenant.com")

    pagina = await client.get("/correcoes")

    assert "Valor atual" in pagina.text
    assert "Valor sugerido" in pagina.text
    assert 'class="fonte"' in pagina.text
    assert "<td>—</td>" in pagina.text
