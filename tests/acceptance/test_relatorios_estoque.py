"""Aceitação P1 — Relatório de estoque (REL-06..REL-10, REL-38).

Prova os critérios da story pelo fluxo HTTP real, com o histórico versionado
semeado por empresa.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from httpx import AsyncClient
from relatorios_suporte import (
    JANEIRO,
    QUANDO,
    celulas_da_linha,
    criar_conta,
    login,
    semear,
)
from sqlalchemy.orm import Session, sessionmaker

_ESTOQUE = "/relatorios/estoque"


def _item(
    fabrica: sessionmaker[Session],
    empresa_id: UUID,
    sku: str,
    *,
    nome: str = "Caixa",
    categoria: str = "",
    local: str = "",
    quantidade: int = 1,
    minimo: int = 5,
    quando: datetime = QUANDO,
) -> None:
    """Semeia um item de estoque no histórico da empresa."""
    semear(
        fabrica,
        empresa_id,
        "estoque",
        sku,
        quando,
        nome=nome,
        categoria=categoria,
        local=local,
        quantidade=quantidade,
        minimo=minimo,
    )


async def test_est_01_renderiza_apenas_empresa_da_sessao(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC1: a página renderiza só registros da empresa da sessão."""
    dados_a = await criar_conta(client, "A", "a@tenant.com")
    dados_b = await criar_conta(client, "B", "b@tenant.com")
    _item(fabrica_sync, UUID(dados_a["empresa_id"]), "SKU-A", local="A1")
    _item(fabrica_sync, UUID(dados_b["empresa_id"]), "SKU-B", local="B1")
    await login(client, "a@tenant.com")

    pagina = await client.get(_ESTOQUE)

    assert pagina.status_code == 200
    assert "Relatórios · Estoque" in pagina.text
    assert "<td>SKU-A</td>" in pagina.text
    assert "SKU-B" not in pagina.text


async def test_est_02_lista_abaixo_do_minimo_com_campos(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC2: item abaixo do mínimo com sku, nome, quantidade, mínimo e local."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    _item(
        fabrica_sync,
        UUID(dados["empresa_id"]),
        "SKU-1",
        nome="Caixa",
        local="A1",
        quantidade=1,
        minimo=5,
    )
    await login(client, "a@tenant.com")

    pagina = await client.get(_ESTOQUE)

    assert celulas_da_linha(pagina.text, "SKU-1")[:6] == [
        "SKU-1",
        "Caixa",
        "",
        "A1",
        "1",
        "5",
    ]
    assert celulas_da_linha(pagina.text, "SKU-1")[-1] == "Abaixo do mínimo"


async def test_est_03_classifica_excedente_acima_do_dobro(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC3: excedente quando quantidade > mínimo * 2; o dobro exato é Normal."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _item(fabrica_sync, empresa_id, "EX", quantidade=30, minimo=5)
    _item(fabrica_sync, empresa_id, "LIM", quantidade=10, minimo=5)
    await login(client, "a@tenant.com")

    pagina = await client.get(_ESTOQUE)

    assert celulas_da_linha(pagina.text, "EX")[-1] == "Excedente"
    assert celulas_da_linha(pagina.text, "LIM")[-1] == "Normal"


async def test_est_38_minimo_zero_nunca_e_excedente(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """REL-38: mínimo == 0 nunca classifica excedente (sem divisão por zero)."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    _item(fabrica_sync, UUID(dados["empresa_id"]), "ZERO", quantidade=100, minimo=0)
    await login(client, "a@tenant.com")

    pagina = await client.get(_ESTOQUE)

    assert pagina.status_code == 200
    assert celulas_da_linha(pagina.text, "ZERO")[-1] == "Normal"
    assert "Excedente" not in pagina.text


async def test_est_04_conta_itens_por_local(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC4: mostra a contagem de itens por local."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _item(fabrica_sync, empresa_id, "S1", local="A1")
    _item(fabrica_sync, empresa_id, "S2", local="A1")
    _item(fabrica_sync, empresa_id, "S3", local="B1")
    await login(client, "a@tenant.com")

    pagina = await client.get(_ESTOQUE)

    assert "Itens por local" in pagina.text
    assert "A1: 2" in pagina.text
    assert "B1: 1" in pagina.text


async def test_est_05_conta_itens_por_categoria(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC5: mostra a contagem de itens por categoria."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _item(fabrica_sync, empresa_id, "S1", categoria="Embalagem")
    _item(fabrica_sync, empresa_id, "S2", categoria="Embalagem")
    _item(fabrica_sync, empresa_id, "S3", categoria="Base")
    await login(client, "a@tenant.com")

    pagina = await client.get(_ESTOQUE)

    assert "Itens por categoria" in pagina.text
    assert "Embalagem: 2" in pagina.text
    assert "Base: 1" in pagina.text


async def test_est_06_recorte_de_periodo_inclusivo(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC6: o período informado recorta o conjunto de forma inclusiva."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _item(fabrica_sync, empresa_id, "JAN", quando=JANEIRO)
    _item(fabrica_sync, empresa_id, "JUN", quando=QUANDO)
    await login(client, "a@tenant.com")

    filtrado = await client.get(
        _ESTOQUE, params={"desde": "2026-06-01", "ate": "2026-06-30"}
    )
    total = await client.get(_ESTOQUE)

    assert "<td>JUN</td>" in filtrado.text
    assert "JAN" not in filtrado.text
    assert "<td>JAN</td>" in total.text
    assert "<td>JUN</td>" in total.text


async def test_est_37_empresa_sem_registros_exibe_estado_vazio(
    client: AsyncClient,
) -> None:
    """REL-37: empresa sem registros exibe estado vazio claro, sem erro."""
    await criar_conta(client, "A", "a@tenant.com")
    await login(client, "a@tenant.com")

    pagina = await client.get(_ESTOQUE)

    assert pagina.status_code == 200
    assert "Nenhum item de estoque no período." in pagina.text
