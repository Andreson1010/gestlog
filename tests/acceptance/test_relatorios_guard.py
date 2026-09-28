"""Aceitação P1 — Guarda de acesso dos relatórios (REL-25..REL-27)."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import AsyncClient
from relatorios_suporte import (
    DOMINIOS,
    criar_conta,
    criar_usuario,
    login,
)
from sqlalchemy.ext.asyncio import AsyncEngine

ROTAS_PAGINA = [f"/relatorios/{dominio}" for dominio in DOMINIOS]
ROTAS_EXPORT = [f"/relatorios/{dominio}/exportar" for dominio in DOMINIOS]
ROTAS = ROTAS_PAGINA + ROTAS_EXPORT


@pytest.mark.parametrize("rota", ROTAS)
async def test_guard_01_sem_sessao_responde_401(client: AsyncClient, rota: str) -> None:
    """AC1: visitante sem sessão recebe 401 em página e exportação."""
    assert (await client.get(rota)).status_code == 401


@pytest.mark.parametrize("rota", ROTAS)
async def test_guard_02_operador_responde_403(
    client: AsyncClient,
    motores,
    rota: str,
) -> None:
    """AC2: usuário operador recebe 403 em página e exportação."""
    motor_async, _ = motores
    dados = await criar_conta(client, "A", "admin@tenant.com")
    await criar_usuario(
        motor_async, UUID(dados["empresa_id"]), "op@tenant.com", "operador"
    )
    await login(client, "op@tenant.com")

    assert (await client.get(rota)).status_code == 403


@pytest.mark.parametrize("rota", ROTAS)
async def test_guard_03_admin_responde_200(client: AsyncClient, rota: str) -> None:
    """AC3: usuário admin recebe 200 nas rotas de domínio e exportação."""
    await criar_conta(client, "A", "admin@tenant.com")
    await login(client, "admin@tenant.com")

    assert (await client.get(rota)).status_code == 200


@pytest.mark.parametrize("rota", ROTAS_PAGINA + ROTAS_EXPORT)
async def test_guard_03b_gestor_responde_200(
    client: AsyncClient,
    motores: tuple[AsyncEngine, object],
    rota: str,
) -> None:
    """AC3: usuário gestor recebe 200 nas rotas de domínio e exportação."""
    motor_async, _ = motores
    dados = await criar_conta(client, "A", "admin@tenant.com")
    await criar_usuario(
        motor_async, UUID(dados["empresa_id"]), "gestor@tenant.com", "gestor"
    )
    await login(client, "gestor@tenant.com")

    assert (await client.get(rota)).status_code == 200


async def test_guard_dominio_invalido_responde_404(
    client: AsyncClient,
) -> None:
    """API: domínio fora dos suportados responde 404."""
    await criar_conta(client, "A", "admin@tenant.com")
    await login(client, "admin@tenant.com")

    assert (await client.get("/relatorios/financeiro")).status_code == 404
    assert (await client.get("/relatorios/financeiro/exportar")).status_code == 404
