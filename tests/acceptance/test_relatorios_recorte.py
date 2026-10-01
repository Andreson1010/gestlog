"""Aceitação P1 — Recorte por empresa e período (REL-19..REL-24, REL-34, REL-35)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from httpx import AsyncClient
from relatorios_suporte import (
    JANEIRO,
    QUANDO,
    criar_conta,
    login,
    semear,
)
from sqlalchemy.orm import Session, sessionmaker

_ESTOQUE = "/relatorios/estoque"
_INICIO = datetime(2026, 6, 1, 0, 0, 0, 0, tzinfo=UTC)
_FIM = datetime(2026, 6, 30, 23, 59, 59, 999999, tzinfo=UTC)
_ANTES = datetime(2026, 5, 31, 23, 59, 59, 999999, tzinfo=UTC)


def _item(
    fabrica: sessionmaker[Session],
    empresa_id: UUID,
    chave: str,
    quando: datetime = QUANDO,
) -> None:
    """Semeia um item de estoque com o timestamp dado."""
    semear(
        fabrica,
        empresa_id,
        "estoque",
        chave,
        quando,
        nome="Caixa",
        quantidade=1,
        minimo=5,
    )


async def test_rec_01_empresa_vem_do_membership_ignorando_empresa_id(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC1/AC2: deriva a empresa do Membership e ignora empresa_id do cliente."""
    dados_a = await criar_conta(client, "A", "a@tenant.com")
    dados_b = await criar_conta(client, "B", "b@tenant.com")
    _item(fabrica_sync, UUID(dados_a["empresa_id"]), "SKU-A")
    _item(fabrica_sync, UUID(dados_b["empresa_id"]), "SKU-B")
    await login(client, "a@tenant.com")

    empresa_b = dados_b["empresa_id"]
    pagina = await client.get(_ESTOQUE, params={"empresa_id": empresa_b})
    exportacao = await client.get(
        "/relatorios/estoque/exportar", params={"empresa_id": empresa_b}
    )

    assert "<td>SKU-A</td>" in pagina.text
    assert "SKU-B" not in pagina.text
    assert "SKU-B" not in exportacao.content.decode("utf-8-sig")


async def test_rec_03_sem_periodo_considera_todo_historico(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC3: sem de/até considera todo o histórico disponível."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _item(fabrica_sync, empresa_id, "JAN", JANEIRO)
    _item(fabrica_sync, empresa_id, "JUN", QUANDO)
    await login(client, "a@tenant.com")

    pagina = await client.get(_ESTOQUE)

    assert "<td>JAN</td>" in pagina.text
    assert "<td>JUN</td>" in pagina.text


async def test_rec_04_limites_utc_inclusivos(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC4: inclui importado_em no intervalo UTC inclusivo do dia."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _item(fabrica_sync, empresa_id, "INICIO", _INICIO)
    _item(fabrica_sync, empresa_id, "FIM", _FIM)
    _item(fabrica_sync, empresa_id, "ANTES", _ANTES)
    await login(client, "a@tenant.com")

    pagina = await client.get(
        _ESTOQUE, params={"desde": "2026-06-01", "ate": "2026-06-30"}
    )

    assert "<td>INICIO</td>" in pagina.text
    assert "<td>FIM</td>" in pagina.text
    assert "ANTES" not in pagina.text


async def test_rec_05_de_igual_a_ate_inclui_o_dia(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC5: quando de == até inclui os registros daquele dia."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _item(fabrica_sync, empresa_id, "NO-DIA", datetime(2026, 6, 10, 12, tzinfo=UTC))
    _item(fabrica_sync, empresa_id, "FORA", datetime(2026, 6, 11, 12, tzinfo=UTC))
    await login(client, "a@tenant.com")

    pagina = await client.get(
        _ESTOQUE, params={"desde": "2026-06-10", "ate": "2026-06-10"}
    )

    assert "<td>NO-DIA</td>" in pagina.text
    assert "FORA" not in pagina.text


async def test_rec_23_persiste_de_e_ate_no_formulario(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """AC6: a página re-renderizada mantém de/até nos campos do formulário."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    _item(fabrica_sync, UUID(dados["empresa_id"]), "SKU-1")
    await login(client, "a@tenant.com")

    pagina = await client.get(
        _ESTOQUE, params={"desde": "2026-06-01", "ate": "2026-06-30"}
    )

    assert 'value="2026-06-01"' in pagina.text
    assert 'value="2026-06-30"' in pagina.text


async def test_rec_24_apenas_de_aplica_limite_inferior(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """Edge: só de aplica apenas o limite inferior, inclusivo."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _item(fabrica_sync, empresa_id, "JAN", JANEIRO)
    _item(fabrica_sync, empresa_id, "JUN", QUANDO)
    await login(client, "a@tenant.com")

    pagina = await client.get(_ESTOQUE, params={"desde": "2026-06-01"})

    assert "<td>JUN</td>" in pagina.text
    assert "JAN" not in pagina.text


async def test_rec_24b_apenas_ate_aplica_limite_superior(
    client: AsyncClient,
    fabrica_sync: sessionmaker[Session],
) -> None:
    """Edge: só até aplica apenas o limite superior, inclusivo."""
    dados = await criar_conta(client, "A", "a@tenant.com")
    empresa_id = UUID(dados["empresa_id"])
    _item(fabrica_sync, empresa_id, "JAN", JANEIRO)
    _item(fabrica_sync, empresa_id, "JUN", QUANDO)
    await login(client, "a@tenant.com")

    pagina = await client.get(_ESTOQUE, params={"ate": "2026-01-31"})

    assert "<td>JAN</td>" in pagina.text
    assert "JUN" not in pagina.text


async def test_rec_34_de_posterior_a_ate_responde_422(
    client: AsyncClient,
) -> None:
    """REL-34: de > até responde 422 na página e na exportação."""
    await criar_conta(client, "A", "a@tenant.com")
    await login(client, "a@tenant.com")
    params = {"desde": "2026-09-30", "ate": "2026-09-01"}

    assert (await client.get(_ESTOQUE, params=params)).status_code == 422
    assert (
        await client.get("/relatorios/estoque/exportar", params=params)
    ).status_code == 422


async def test_rec_35_data_invalida_responde_422(client: AsyncClient) -> None:
    """REL-35: data inválida responde 422 do framework."""
    await criar_conta(client, "A", "a@tenant.com")
    await login(client, "a@tenant.com")

    resposta = await client.get(_ESTOQUE, params={"desde": "abc"})

    assert resposta.status_code == 422
