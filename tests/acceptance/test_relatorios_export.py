"""Aceitação P1 — Exportação CSV por domínio (REL-28..REL-33)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from httpx import AsyncClient
from relatorios_suporte import (
    QUANDO,
    celulas_da_linha,
    criar_conta,
    ler_csv,
    login,
    semear,
)
from sqlalchemy.orm import Session, sessionmaker

_ESTOQUE = "/relatorios/estoque"
_EXPORT = "/relatorios/estoque/exportar"


def _item(
    fabrica: sessionmaker[Session],
    empresa_id: UUID,
    chave: str,
    **payload: object,
) -> None:
    """Semeia um item de estoque com o payload informado."""
    base: dict[str, object] = {
        "nome": "Caixa",
        "categoria": "Embalagem",
        "local": "A1",
        "quantidade": 1,
        "minimo": 5,
    }
    base.update(payload)
    semear(fabrica, empresa_id, "estoque", chave, QUANDO, **base)


async def test_exp_01_linhas_correspondem_a_tabela_da_tela(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC1/AC9: cada linha do CSV corresponde exatamente à linha da tela."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _item(fabrica_sync, empresa_id, "S1")
    _item(
        fabrica_sync,
        empresa_id,
        "S2",
        nome="Pallet",
        categoria="Base",
        local="B1",
        quantidade=30,
        minimo=5,
    )
    await login(client, "a@tenant.com")

    pagina = await client.get(_ESTOQUE)
    linhas = ler_csv(await _baixar(client))

    assert linhas[0] == [
        "SKU",
        "Nome",
        "Categoria",
        "Local",
        "Quantidade",
        "Mínimo",
        "Situação",
    ]
    assert len(linhas) == 3
    for linha in linhas[1:]:
        assert celulas_da_linha(pagina.text, linha[0]) == linha


async def test_exp_09_data_do_csv_igual_a_da_tela(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC9: o formato de data do CSV é idêntico ao exibido na tabela."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    semear(
        fabrica_sync,
        UUID(dados["empresa_id"]),
        "transporte",
        "R1",
        QUANDO,
        origem="SP",
        destino="CWB",
        peso_kg=10.0,
        status="entregue",
        previsao_entrega=datetime(2026, 6, 10, tzinfo=UTC),
        data_entrega=datetime(2026, 6, 15, tzinfo=UTC),
    )
    await login(client, "a@tenant.com")

    pagina = await client.get("/relatorios/transporte")
    linhas = ler_csv(await _baixar(client, "transporte"))

    assert "2026-06-10T00:00:00" in pagina.text
    assert linhas[1][5] == "2026-06-10T00:00:00"
    assert celulas_da_linha(pagina.text, "R1") == linhas[1]


async def test_exp_02_content_disposition_e_nome_do_arquivo(
    client: AsyncClient,
) -> None:
    """AC2: Content-Disposition attachment com domínio e período no nome."""
    await criar_conta(client, "A", "a@tenant.com")
    await login(client, "a@tenant.com")

    sem_data = await client.get(_EXPORT)
    so_de = await client.get(_EXPORT, params={"desde": "2026-06-01"})
    so_ate = await client.get(_EXPORT, params={"ate": "2026-06-30"})
    ambos = await client.get(
        _EXPORT, params={"desde": "2026-06-01", "ate": "2026-06-30"}
    )

    assert (
        sem_data.headers["content-disposition"]
        == 'attachment; filename="relatorio-estoque.csv"'
    )
    assert (
        so_de.headers["content-disposition"]
        == 'attachment; filename="relatorio-estoque-2026-06-01.csv"'
    )
    assert (
        so_ate.headers["content-disposition"]
        == 'attachment; filename="relatorio-estoque-2026-06-30.csv"'
    )
    assert (
        ambos.headers["content-disposition"]
        == 'attachment; filename="relatorio-estoque-2026-06-01_2026-06-30.csv"'
    )


async def test_exp_03_conteudo_utf8_com_bom(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC3: conteúdo UTF-8 com BOM (Excel pt-BR)."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    _item(fabrica_sync, UUID(dados["empresa_id"]), "S1", nome="Ação")
    await login(client, "a@tenant.com")

    conteudo = await _baixar(client)

    assert conteudo.startswith(b"\xef\xbb\xbf")
    assert conteudo.decode("utf-8-sig").splitlines()[0].startswith("SKU;Nome")
    assert "Ação" in conteudo.decode("utf-8-sig")


async def test_exp_04_escapa_campos_rfc_4180(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC4: campos com ;, aspas e quebra de linha permanecem parseáveis."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    _item(
        fabrica_sync,
        UUID(dados["empresa_id"]),
        "S1",
        nome='Caixa "grande"',
        categoria="linha\nquebrada",
        local="A;1",
    )
    await login(client, "a@tenant.com")

    linhas = ler_csv(await _baixar(client))

    assert linhas[1][1] == 'Caixa "grande"'
    assert linhas[1][2] == "linha\nquebrada"
    assert linhas[1][3] == "A;1"


async def test_exp_05_neutraliza_formulas_em_texto(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC5: campos de texto iniciados por = + - @ são neutralizados."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _item(fabrica_sync, empresa_id, "S1", nome="=CMD()", local="+A1")
    _item(fabrica_sync, empresa_id, "S2", nome="-perigo", local="@x")
    await login(client, "a@tenant.com")

    linhas = ler_csv(await _baixar(client))

    por_sku = {linha[0]: linha for linha in linhas[1:]}
    assert por_sku["S1"][1] == "'=CMD()"
    assert por_sku["S1"][3] == "'+A1"
    assert por_sku["S2"][1] == "'-perigo"
    assert por_sku["S2"][3] == "'@x"


async def test_exp_05b_nao_neutraliza_numericos(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC5: campos numéricos não recebem prefixo de neutralização."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    _item(fabrica_sync, UUID(dados["empresa_id"]), "S1", quantidade=5, minimo=0)
    await login(client, "a@tenant.com")

    linha = ler_csv(await _baixar(client))[1]

    assert linha[4] == "5"
    assert linha[5] == "0"


async def test_exp_06_export_sem_sessao_401(client: AsyncClient) -> None:
    """AC6: exportação sem sessão responde 401."""
    assert (await client.get(_EXPORT)).status_code == 401


async def test_exp_07_nunca_inclui_outra_empresa(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC7: a exportação nunca inclui registros de outra empresa."""
    dados_a = await criar_conta(client, "A", "a@tenant.com")
    dados_b = await criar_conta(client, "B", "b@tenant.com")
    _item(fabrica_sync, UUID(dados_a["empresa_id"]), "SKU-A")
    _item(fabrica_sync, UUID(dados_b["empresa_id"]), "SKU-B")
    await login(client, "a@tenant.com")

    conteudo = (await _baixar(client)).decode("utf-8-sig")

    assert "SKU-A" in conteudo
    assert "SKU-B" not in conteudo


async def test_exp_08_empresa_vazia_apenas_cabecalho(
    client: AsyncClient,
) -> None:
    """AC8: empresa sem registros devolve CSV apenas com o cabeçalho (200)."""
    await criar_conta(client, "A", "a@tenant.com")
    await login(client, "a@tenant.com")

    resposta = await client.get(_EXPORT)
    linhas = ler_csv(resposta.content)

    assert resposta.status_code == 200
    assert len(linhas) == 1
    assert linhas[0][0] == "SKU"


async def _baixar(client: AsyncClient, dominio: str = "estoque") -> bytes:
    """Baixa o CSV do domínio para a empresa da sessão."""
    resposta = await client.get(f"/relatorios/{dominio}/exportar")
    assert resposta.status_code == 200, resposta.text
    return resposta.content
