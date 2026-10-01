"""Aceitação P1 — Relatório de fornecedores (REL-15..REL-18, REL-40)."""

from __future__ import annotations

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

_FORNECEDORES = "/relatorios/fornecedores"


def _fornecedor(
    fabrica: sessionmaker[Session],
    empresa_id: UUID,
    chave: str,
    *,
    nome: str = "TransLog",
    categoria: str = "",
    prazo_dias: int = 0,
    avaliacao: float = 0.0,
    ativo: bool = True,
    quando=QUANDO,
) -> None:
    """Semeia um fornecedor no histórico da empresa."""
    semear(
        fabrica,
        empresa_id,
        "fornecedores",
        chave,
        quando,
        nome=nome,
        categoria=categoria,
        prazo_dias=prazo_dias,
        avaliacao=avaliacao,
        ativo=ativo,
    )


async def test_for_01_renderiza_apenas_empresa_da_sessao(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC1: a página renderiza só registros da empresa da sessão."""
    dados_a = await criar_conta(client, "A", "a@tenant.com")
    dados_b = await criar_conta(client, "B", "b@tenant.com")
    _fornecedor(fabrica_sync, UUID(dados_a["empresa_id"]), "F-A", nome="Alfa")
    _fornecedor(fabrica_sync, UUID(dados_b["empresa_id"]), "F-B", nome="Beta")
    await login(client, "a@tenant.com")

    pagina = await client.get(_FORNECEDORES)

    assert pagina.status_code == 200
    assert "Relatórios · Fornecedores" in pagina.text
    assert "<td>F-A</td>" in pagina.text
    assert "F-B" not in pagina.text


async def test_for_02_distribuicao_ativos_e_inativos(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC2: mostra a distribuição de fornecedores ativos e inativos."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _fornecedor(fabrica_sync, empresa_id, "F1", ativo=True)
    _fornecedor(fabrica_sync, empresa_id, "F2", ativo=True)
    _fornecedor(fabrica_sync, empresa_id, "F3", ativo=False)
    await login(client, "a@tenant.com")

    pagina = await client.get(_FORNECEDORES)

    assert "Distribuição por situação" in pagina.text
    assert "Ativos: 2" in pagina.text
    assert "Inativos: 1" in pagina.text


async def test_for_03_indicadores_medios(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC3: mostra médias de avaliação e prazo dos fornecedores."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _fornecedor(fabrica_sync, empresa_id, "F1", avaliacao=0.0, prazo_dias=0)
    _fornecedor(fabrica_sync, empresa_id, "F2", avaliacao=4.0, prazo_dias=10)
    await login(client, "a@tenant.com")

    pagina = await client.get(_FORNECEDORES)

    assert "Indicadores" in pagina.text
    assert "Avaliação média: 2.0" in pagina.text
    assert "Prazo médio: 5.0" in pagina.text


async def test_for_40_avaliacao_zero_e_prazo_zero_sao_reais(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """REL-40: avaliação 0.0 e prazo 0 exibidos como valores reais, não ausentes."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    _fornecedor(
        fabrica_sync,
        UUID(dados["empresa_id"]),
        "F1",
        avaliacao=0.0,
        prazo_dias=0,
    )
    await login(client, "a@tenant.com")

    pagina = await client.get(_FORNECEDORES)

    assert celulas_da_linha(pagina.text, "F1")[-3:] == ["0", "0.0", "Ativo"]
    assert "Avaliação média: 0.0" in pagina.text
    assert "Prazo médio: 0.0" in pagina.text


async def test_for_04_conta_fornecedores_por_categoria(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC4: mostra a contagem de fornecedores por categoria."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _fornecedor(fabrica_sync, empresa_id, "F1", categoria="Transporte")
    _fornecedor(fabrica_sync, empresa_id, "F2", categoria="Transporte")
    _fornecedor(fabrica_sync, empresa_id, "F3", categoria="Insumos")
    await login(client, "a@tenant.com")

    pagina = await client.get(_FORNECEDORES)

    assert "Fornecedores por categoria" in pagina.text
    assert "Transporte: 2" in pagina.text
    assert "Insumos: 1" in pagina.text


async def test_for_05_recorte_de_periodo_inclusivo(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC5: o período informado recorta o conjunto de forma inclusiva."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _fornecedor(fabrica_sync, empresa_id, "JAN", quando=JANEIRO)
    _fornecedor(fabrica_sync, empresa_id, "JUN", quando=QUANDO)
    await login(client, "a@tenant.com")

    filtrado = await client.get(
        _FORNECEDORES, params={"desde": "2026-06-01", "ate": "2026-06-30"}
    )

    assert "<td>JUN</td>" in filtrado.text
    assert "JAN" not in filtrado.text
