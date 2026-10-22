"""Fixtures compartilhadas e modelo de chat falso (sem rede)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.tools import BaseTool
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from gestlog.config import Settings
from gestlog.db import build_engine, build_session_factory, init_db

VAR_POSTGRES = "GESTLOG_TEST_DATABASE_URL"


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
        tokens: int = 0,
    ) -> None:
        self._routes = list(routes or [])
        self._final = final
        self._tool_calls = list(tool_calls or [])
        self._tokens = tokens
        self._step = 0
        self.bound_tools: list[BaseTool] = []
        self.mensagens_recebidas: list[list[BaseMessage]] = []

    def _uso(self) -> dict[str, int] | None:
        """Metadados de uso devolvidos pelo modelo, quando configurados."""
        if not self._tokens:
            return None
        return {
            "input_tokens": self._tokens,
            "output_tokens": 0,
            "total_tokens": self._tokens,
        }

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
        uso = self._uso()
        if self._step < len(self._tool_calls):
            calls = self._tool_calls[self._step]
            self._step += 1
            return AIMessage(content="", tool_calls=calls, usage_metadata=uso)
        self._step += 1
        return AIMessage(content=self._final, usage_metadata=uso)


@pytest.fixture
def fake_model_cls() -> type[FakeChatModel]:
    return FakeChatModel


@pytest.fixture(scope="session")
def url_postgres() -> str | None:
    """URL do Postgres da matriz de dialetos (``GESTLOG_TEST_DATABASE_URL``)."""
    return os.environ.get(VAR_POSTGRES) or None


@pytest.fixture(scope="session")
def engine_postgres(url_postgres: str | None) -> Iterator[Engine | None]:
    """Engine do Postgres de teste com o schema criado; ``None`` sem a variável."""
    if url_postgres is None:
        yield None
        return
    engine = create_engine(url_postgres)
    init_db(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(engine_postgres: Engine | None) -> Iterator[Session]:
    """Sessão SQLAlchemy com as tabelas criadas, isolada por teste.

    Sem ``GESTLOG_TEST_DATABASE_URL`` usa SQLite em memória. Com a variável
    definida, roda no Postgres da matriz de dialetos: cada teste escreve dentro
    de uma transação externa e os ``commit`` viram releases de savepoint, tudo
    revertido no teardown — o mesmo isolamento do banco em memória.
    """
    if engine_postgres is None:
        settings = Settings(_env_file=None, database_url="sqlite+pysqlite:///:memory:")
        engine = build_engine(settings)
        init_db(engine)
        factory = build_session_factory(engine)
        with factory() as session:
            yield session
        return
    with engine_postgres.connect() as conexao:
        transacao = conexao.begin()
        session = Session(
            bind=conexao,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            session.close()
            transacao.rollback()
