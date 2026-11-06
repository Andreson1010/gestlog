"""Testes do rate limiting em memória (AD-015)."""

from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from gestlog.config import Settings, get_settings
from gestlog.web.rate_limit import RateLimiter, limitar


def test_limitador_permite_ate_o_limite() -> None:
    limitador = RateLimiter()

    resultados = [limitador.permitir("rota:ip", 3, 60) for _ in range(3)]

    assert resultados == [True, True, True]
    assert limitador.permitir("rota:ip", 3, 60) is False


def test_limitador_chave_isolada_nao_consome_outra() -> None:
    limitador = RateLimiter()

    assert limitador.permitir("a:1", 1, 60) is True

    assert limitador.permitir("a:2", 1, 60) is True
    assert limitador.permitir("b:1", 1, 60) is True
    assert limitador.permitir("a:1", 1, 60) is False


def test_limitador_janela_descartada(monkeypatch: pytest.MonkeyPatch) -> None:
    limite = RateLimiter()
    relógio = {"agora": 100.0}
    monkeypatch.setattr(
        "gestlog.web.rate_limit.time.monotonic", lambda: relógio["agora"]
    )

    assert limite.permitir("rota:ip", 1, 60) is True
    assert limite.permitir("rota:ip", 1, 60) is False
    relógio["agora"] += 61.0

    assert limite.permitir("rota:ip", 1, 60) is True


def test_limitador_poda_chaves_sem_marca_viva(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chaves expiradas são removidas quando o dicionário passa do teto."""
    monkeypatch.setattr("gestlog.web.rate_limit._MAX_CHAVES", 3)
    relógio = {"agora": 100.0}
    monkeypatch.setattr(
        "gestlog.web.rate_limit.time.monotonic", lambda: relógio["agora"]
    )
    limite = RateLimiter()
    for i in range(3):
        limite.permitir(f"rota:{i}", 1, 60)
    relógio["agora"] += 61.0

    limite.permitir("rota:nova", 1, 60)

    assert "rota:0" not in limite._tentativas
    assert "rota:1" not in limite._tentativas
    assert "rota:2" not in limite._tentativas
    assert "rota:nova" in limite._tentativas


def _settings_com_limite(tentativas: int) -> Settings:
    return Settings(
        _env_file=None,
        database_url="sqlite+aiosqlite:///:memory:",
        auth_secret="segredo-de-teste-com-pelo-menos-32-bytes",
        auth_cookie_secure=False,
        rate_limit_tentativas=tentativas,
    )


async def test_rota_excede_limite_e_recebe_429() -> None:
    app = FastAPI()
    settings = _settings_com_limite(2)
    app.dependency_overrides[get_settings] = lambda: settings

    @app.get("/protegida", dependencies=[Depends(limitar("teste"))])
    async def protegida() -> dict[str, str]:
        return {"ok": "sim"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as cliente:
        respostas = [
            await cliente.get("/protegida"),
            await cliente.get("/protegida"),
            await cliente.get("/protegida"),
        ]

    status_codes = [resposta.status_code for resposta in respostas]
    assert status_codes == [200, 200, 429]


async def test_limitador_usa_janela_da_config() -> None:
    """A dependência lê o limite do ``Settings`` corrente, não um valor fixo."""
    app = FastAPI()
    app.dependency_overrides[get_settings] = lambda: _settings_com_limite(1)

    @app.get("/protegida", dependencies=[Depends(limitar("teste"))])
    async def protegida() -> dict[str, str]:
        return {"ok": "sim"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as cliente:
        primeira = await cliente.get("/protegida")
        segunda = await cliente.get("/protegida")

    assert primeira.status_code == 200
    assert segunda.status_code == 429
