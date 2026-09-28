"""Aceitação P1 — Relatório de transporte (REL-11..REL-14, REL-39)."""

from __future__ import annotations

import re
from datetime import UTC, datetime
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

_TRANSPORTE = "/relatorios/transporte"


def _registro(
    fabrica: sessionmaker[Session],
    empresa_id: UUID,
    chave: str,
    *,
    origem: str = "SP",
    destino: str = "CWB",
    peso_kg: float = 10.0,
    status: str = "entregue",
    previsao_entrega: datetime | None = None,
    data_entrega: datetime | None = None,
    quando=QUANDO,
) -> None:
    """Semeia um registro de transporte no histórico da empresa."""
    semear(
        fabrica,
        empresa_id,
        "transporte",
        chave,
        quando,
        origem=origem,
        destino=destino,
        peso_kg=peso_kg,
        status=status,
        previsao_entrega=previsao_entrega,
        data_entrega=data_entrega,
    )


async def test_tr_01_renderiza_apenas_empresa_da_sessao(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC1: a página renderiza só registros da empresa da sessão."""
    dados_a = await criar_conta(client, "A", "a@tenant.com")
    dados_b = await criar_conta(client, "B", "b@tenant.com")
    _registro(fabrica_sync, UUID(dados_a["empresa_id"]), "R-A")
    _registro(fabrica_sync, UUID(dados_b["empresa_id"]), "R-B")
    await login(client, "a@tenant.com")

    pagina = await client.get(_TRANSPORTE)

    assert pagina.status_code == 200
    assert "Relatórios · Transporte" in pagina.text
    assert "<td>R-A</td>" in pagina.text
    assert "R-B" not in pagina.text


async def test_tr_02_conta_registros_por_status(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC2: mostra a contagem de registros por status."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _registro(fabrica_sync, empresa_id, "R1", status="entregue")
    _registro(fabrica_sync, empresa_id, "R2", status="entregue")
    _registro(fabrica_sync, empresa_id, "R3", status="em_transito")
    await login(client, "a@tenant.com")

    pagina = await client.get(_TRANSPORTE)

    assert "Registros por status" in pagina.text
    assert "entregue: 2" in pagina.text
    assert "em_transito: 1" in pagina.text


async def test_tr_03_soma_peso_por_rota_incluindo_zero(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC3/REL-39: soma peso por par origem→destino, sem omitir rota zero."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _registro(fabrica_sync, empresa_id, "R1", origem="SP", destino="CWB", peso_kg=10)
    _registro(fabrica_sync, empresa_id, "R2", origem="SP", destino="CWB", peso_kg=5)
    _registro(fabrica_sync, empresa_id, "R3", origem="REC", destino="FOR", peso_kg=0)
    await login(client, "a@tenant.com")

    pagina = await client.get(_TRANSPORTE)

    assert "Peso por rota" in pagina.text
    assert "SP → CWB: 15.0" in pagina.text
    assert "REC → FOR: 0.0" in pagina.text


async def test_tr_04_classifica_atraso_apos_a_previsao(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC4: atraso quando data_entrega > previsao_entrega (ambos preenchidos)."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _registro(
        fabrica_sync,
        empresa_id,
        "ATRASADO",
        previsao_entrega=datetime(2026, 6, 1, tzinfo=UTC),
        data_entrega=datetime(2026, 6, 5, tzinfo=UTC),
    )
    _registro(
        fabrica_sync,
        empresa_id,
        "PRAZO",
        previsao_entrega=datetime(2026, 6, 5, tzinfo=UTC),
        data_entrega=datetime(2026, 6, 5, tzinfo=UTC),
    )
    _registro(fabrica_sync, empresa_id, "SEM-DATA")
    await login(client, "a@tenant.com")

    pagina = await client.get(_TRANSPORTE)

    assert celulas_da_linha(pagina.text, "ATRASADO")[-1] == "Atrasado"
    assert celulas_da_linha(pagina.text, "PRAZO")[-1] == "No prazo"
    assert celulas_da_linha(pagina.text, "SEM-DATA")[-1] == "No prazo"
    assert pagina.text.count("Atrasado") == 1


def _contagem_atrasos(html: str) -> str:
    """Extrai o texto do bloco de atrasos (rótulo + número) da página."""
    bloco = re.search(
        r'<div class="bloco">\s*<h2>Atrasos no período</h2>.*?</li>',
        html,
        flags=re.S,
    )
    assert bloco is not None, "bloco de atrasos ausente"
    return " ".join(re.sub(r"<[^>]+>", " ", bloco.group(0)).split())


async def test_tr_04b_mostra_contagem_agregada_de_atrasos(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC4: exibe o número agregado de atrasos, não só a situação por linha."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _registro(
        fabrica_sync,
        empresa_id,
        "ATRASADO",
        previsao_entrega=datetime(2026, 6, 1, tzinfo=UTC),
        data_entrega=datetime(2026, 6, 5, tzinfo=UTC),
    )
    _registro(
        fabrica_sync,
        empresa_id,
        "PRAZO",
        previsao_entrega=datetime(2026, 6, 5, tzinfo=UTC),
        data_entrega=datetime(2026, 6, 5, tzinfo=UTC),
    )
    _registro(fabrica_sync, empresa_id, "SEM-DATA")
    await login(client, "a@tenant.com")

    pagina = await client.get(_TRANSPORTE)

    assert pagina.status_code == 200
    assert _contagem_atrasos(pagina.text) == "Atrasos no período Registros atrasados: 1"


async def test_tr_05_recorte_de_periodo_inclusivo(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC5: o período informado recorta o conjunto de forma inclusiva."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _registro(fabrica_sync, empresa_id, "JAN", quando=JANEIRO)
    _registro(fabrica_sync, empresa_id, "JUN", quando=QUANDO)
    await login(client, "a@tenant.com")

    filtrado = await client.get(
        _TRANSPORTE, params={"desde": "2026-06-01", "ate": "2026-06-30"}
    )

    assert "<td>JUN</td>" in filtrado.text
    assert "JAN" not in filtrado.text
