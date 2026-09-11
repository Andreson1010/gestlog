"""Interface de linha de comando (REPL) do sistema multiagente."""

from __future__ import annotations

import logging

from langchain_core.messages import BaseMessage, HumanMessage

from gestlog.config import get_settings
from gestlog.graph import build_graph

_SAIR = {"sair", "exit", "quit"}


def _configurar_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _texto_da_ultima_resposta(messages: list[BaseMessage]) -> str:
    if not messages:
        return ""
    conteudo = messages[-1].content
    return conteudo if isinstance(conteudo, str) else str(conteudo)


def main() -> None:  # pragma: no cover
    """Ponto de entrada ``gestlog``: lê perguntas no terminal até o usuário sair."""
    settings = get_settings()
    _configurar_logging(settings.log_level)
    graph = build_graph(settings=settings)

    print("gestlog — assistente de gestão logística. Digite 'sair' para encerrar.")
    historico: list[BaseMessage] = []
    while True:
        try:
            entrada = input("você> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not entrada or entrada.lower() in _SAIR:
            break
        historico.append(HumanMessage(content=entrada))
        resultado = graph.invoke(
            {"messages": historico},
            config={"recursion_limit": settings.recursion_limit},
        )
        historico = resultado["messages"]
        print(f"gestlog> {_texto_da_ultima_resposta(historico)}")


if __name__ == "__main__":  # pragma: no cover
    main()
