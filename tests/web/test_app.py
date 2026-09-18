"""Testes de integração da factory da aplicação e dos assets."""

from __future__ import annotations

from fastapi.testclient import TestClient

from gestlog.config import Settings
from gestlog.web import create_app


def _client() -> TestClient:
    settings = Settings(_env_file=None, database_url="sqlite+aiosqlite:///:memory:")
    return TestClient(create_app(settings))


def test_pagina_de_login_renderiza() -> None:
    resposta = _client().get("/login")

    assert resposta.status_code == 200
    assert "gestlog" in resposta.text
    assert "/static/app.css" in resposta.text
    assert 'integrity="sha384-' in resposta.text


def test_assets_estaticos_servidos() -> None:
    resposta = _client().get("/static/app.css")

    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/css")
