"""Fixtures compartilhadas e modelo de chat falso (sem rede)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import BaseTool
from sqlalchemy.orm import Session

from gestlog.config import Settings
from gestlog.db import build_engine, build_session_factory, init_db


class FakeChatModel:
    """Modelo fake: fila de rotas para o supervisor e resposta fixa para especialistas.

    - ``routes``: destinos devolvidos em sequência por ``with_structured_output``.
    - ``tool_calls``: lista de passos; cada passo é uma lista de tool calls.
    - ``final``: resposta textual após esgotar os tool calls.
    """

    def __init__(
        self,
        routes: list[str] | None = None,
        final: str = "resposta final",
        tool_calls: list[list[dict[str, Any]]] | None = None,
    ) -> None:
        self._routes = list(routes or [])
        self._final = final
        self._tool_calls = list(tool_calls or [])
        self._step = 0
        self.bound_tools: list[BaseTool] = []
        self.mensagens_recebidas: list[list[BaseMessage]] = []

    def with_structured_output(self, schema: type) -> Any:
        routes = self._routes
        recebidas = self.mensagens_recebidas

        class _Router:
            def invoke(self, messages: list[BaseMessage]) -> Any:
                recebidas.append(messages)
                route = routes.pop(0) if routes else "FINISH"
                return schema(next=route)

        return _Router()

    def bind_tools(self, tools: list[BaseTool]) -> FakeChatModel:
        self.bound_tools = list(tools)
        return self

    def invoke(self, messages: list[BaseMessage]) -> AIMessage:
        self.mensagens_recebidas.append(messages)
        if self._step < len(self._tool_calls):
            calls = self._tool_calls[self._step]
            self._step += 1
            return AIMessage(content="", tool_calls=calls)
        self._step += 1
        return AIMessage(content=self._final)


@pytest.fixture
def fake_model_cls() -> type[FakeChatModel]:
    return FakeChatModel


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Sessão SQLAlchemy em SQLite em memória com todas as tabelas criadas."""
    settings = Settings(_env_file=None, database_url="sqlite+pysqlite:///:memory:")
    engine = build_engine(settings)
    init_db(engine)
    factory = build_session_factory(engine)
    with factory() as session:
        yield session
