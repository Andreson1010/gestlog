"""Testes do helper de contagem de tokens compartilhado pelos agentes."""

from __future__ import annotations

from langchain_core.messages import AIMessage

from gestlog.agents.base import tokens_da_mensagem


def test_tokens_sem_metadata_sao_estimados_nunca_zero() -> None:
    """Sem metadata (ou com total 0) a contagem é estimada; texto nunca rende 0."""
    sem_metadata = AIMessage(content="texto com varias palavras")
    metadata_zero = AIMessage(
        content="outro texto qualquer",
        usage_metadata={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
    )

    assert tokens_da_mensagem(sem_metadata) > 0
    assert tokens_da_mensagem(metadata_zero) > 0


def test_estimativa_cobre_tool_calls_do_payload() -> None:
    """A geração de structured output fica em tool_calls e entra na estimativa."""
    chamadas = [
        {
            "name": "rota",
            "args": {"next": "estoque", "reasoning": "x" * 40},
            "id": "call-1",
            "type": "tool_call",
        }
    ]
    com_chamadas = AIMessage(content="", tool_calls=chamadas)
    vazia = AIMessage(content="")

    assert tokens_da_mensagem(com_chamadas) > tokens_da_mensagem(vazia)
    assert tokens_da_mensagem(com_chamadas) >= len(str(chamadas)) // 4


def test_estimativa_cobre_tool_call_bruta_em_additional_kwargs() -> None:
    """Respostas cruas de function calling carregam a chamada em additional_kwargs."""
    chamadas = [{"function": {"name": "RouteDecision", "arguments": "FINISH"}}]
    mensagem = AIMessage(content="", additional_kwargs={"tool_calls": chamadas})

    assert tokens_da_mensagem(mensagem) >= len(str(chamadas)) // 4
    assert tokens_da_mensagem(mensagem) > 1


def test_tokens_reportados_quando_metadata_presente() -> None:
    mensagem = AIMessage(
        content="x",
        usage_metadata={"input_tokens": 7, "output_tokens": 3, "total_tokens": 10},
    )

    assert tokens_da_mensagem(mensagem) == 10


def test_estimativa_tem_piso_de_um_token() -> None:
    """Mensagens vazias contam 1: a meta é não subestimar (decisão humana 7)."""

    assert tokens_da_mensagem(AIMessage(content="")) == 1
    assert tokens_da_mensagem(AIMessage(content="1234")) == 1


def test_mensagem_ausente_vira_um_token() -> None:

    assert tokens_da_mensagem(None) == 1
