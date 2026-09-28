"""Aceitação P1 — Enablers de dados (REL-01..REL-05, REL-36).

Prova que a ingestão real alimenta o histórico e que o relatório lê o último
snapshot por chave. O backfill Alembic em si é coberto por
``tests/test_migrations.py::test_backfill_historico_dos_catalogos``; aqui se
prova o contrato observável de que dados sem import job (forma do backfill)
aparecem no relatório.
"""

from __future__ import annotations

from uuid import UUID

from httpx import AsyncClient
from relatorios_suporte import (
    JANEIRO,
    QUANDO,
    celulas_da_linha,
    criar_conta,
    importar_arquivo,
    ler_csv,
    login,
    semear,
)
from sqlalchemy.orm import Session, sessionmaker

_ESTOQUE = "/relatorios/estoque"


async def _enviar(
    client: AsyncClient,
    tipo: str,
    conteudo: str,
    nome: str = "dados.csv",
) -> None:
    """Faz upload real do CSV pela rota web de importação."""
    resposta = await client.post(
        "/importar",
        data={"tipo": tipo},
        files={"arquivo": (nome, conteudo.encode("utf-8"), "text/csv")},
    )
    assert resposta.status_code == 200, resposta.text


async def test_en_01_ingestao_de_categoria_alimenta_o_relatorio(
    client: AsyncClient,
) -> None:
    """REL-01/REL-05: a ingestão grava categoria e o relatório a exibe."""
    await criar_conta(client, "A", "a@tenant.com")
    await login(client, "a@tenant.com")

    await _enviar(
        client,
        "estoque",
        "sku,nome,quantidade,minimo,local,categoria\n" "SKU-1,Caixa,1,5,A1,Embalagem\n",
    )
    pagina = await client.get(_ESTOQUE)
    exportacao = await client.get("/relatorios/estoque/exportar")

    assert celulas_da_linha(pagina.text, "SKU-1") == [
        "SKU-1",
        "Caixa",
        "Embalagem",
        "A1",
        "1",
        "5",
        "Abaixo do mínimo",
    ]
    assert "Embalagem: 1" in pagina.text
    assert ler_csv(exportacao.content)[1][2] == "Embalagem"


async def test_en_02_ingestao_de_datas_alimenta_o_atraso(
    client: AsyncClient,
) -> None:
    """REL-02: previsao_entrega/data_entrega da ingestão alimentam o atraso."""
    await criar_conta(client, "A", "a@tenant.com")
    await login(client, "a@tenant.com")

    await _enviar(
        client,
        "transporte",
        "codigo_rastreio,origem,destino,peso_kg,status,previsao_entrega,"
        "data_entrega\nGL-1,SP,CWB,12.5,entregue,2026-09-01,15/09/2026\n",
    )
    pagina = await client.get("/relatorios/transporte")

    assert celulas_da_linha(pagina.text, "GL-1")[-1] == "Atrasado"
    assert "SP → CWB: 12.5" in pagina.text


async def test_en_03_ultimo_snapshot_por_chave_vence(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """REL-03/REL-05: sem período, vale o último snapshot de cada chave."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    importar_arquivo(
        fabrica_sync,
        empresa_id,
        "estoque",
        "sku,nome,quantidade,minimo,local\nSKU-1,Caixa,1,5,A1\n",
    )
    importar_arquivo(
        fabrica_sync,
        empresa_id,
        "estoque",
        "sku,nome,quantidade,minimo,local\nSKU-1,Caixa,40,5,A1\n",
    )
    await login(client, "a@tenant.com")

    pagina = await client.get(_ESTOQUE)

    assert pagina.text.count("<td>SKU-1</td>") == 1
    linha = celulas_da_linha(pagina.text, "SKU-1")
    assert linha[4] == "40"
    assert linha[-1] == "Excedente"


async def test_en_04_linhas_rejeitadas_nao_aparecem(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """REL-05: registros rejeitados não geram snapshot nem aparecem."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    importar_arquivo(
        fabrica_sync,
        empresa_id,
        "estoque",
        "sku,nome,quantidade,minimo\nOK,Caixa,1,5\n,Rejeitado,3,1\n",
    )
    await login(client, "a@tenant.com")

    pagina = await client.get(_ESTOQUE)

    assert "<td>OK</td>" in pagina.text
    assert "Rejeitado" not in pagina.text
    assert celulas_da_linha(pagina.text, "OK")[4] == "1"


async def test_en_05_dados_backfilled_sem_job_sao_visiveis(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """REL-04: dados na forma do backfill (job nulo) aparecem no relatório."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    semear(
        fabrica_sync,
        empresa_id,
        "estoque",
        "PRE-EXISTENTE",
        JANEIRO,
        nome="Caixa antiga",
        quantidade=1,
        minimo=5,
    )
    await login(client, "a@tenant.com")

    sem_periodo = await client.get(_ESTOQUE)
    com_periodo = await client.get(_ESTOQUE, params={"desde": "2026-06-01"})

    assert "<td>PRE-EXISTENTE</td>" in sem_periodo.text
    assert "PRE-EXISTENTE" not in com_periodo.text


async def test_en_36_agregacoes_corretas_em_volume(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """REL-36: as agregações batem com os dados em volume (GROUP BY correto)."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    for indice in range(30):
        local = ("A", "B", "C")[indice % 3]
        semear(
            fabrica_sync,
            empresa_id,
            "estoque",
            f"SKU-{indice}",
            QUANDO,
            nome="Caixa",
            quantidade=1,
            minimo=5,
            local=local,
        )
    await login(client, "a@tenant.com")

    pagina = await client.get(_ESTOQUE)

    assert "A: 10" in pagina.text
    assert "B: 10" in pagina.text
    assert "C: 10" in pagina.text
