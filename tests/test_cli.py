"""Testes dos utilitários da CLI."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from gestlog.cli import _texto_da_ultima_resposta


def test_texto_da_ultima_resposta() -> None:
    assert _texto_da_ultima_resposta([]) == ""
    assert _texto_da_ultima_resposta([AIMessage(content="ok")]) == "ok"
    assert _texto_da_ultima_resposta([HumanMessage(content="oi")]) == "oi"
