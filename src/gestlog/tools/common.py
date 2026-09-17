"""Ferramenta comum de composição da resposta logística.

Fonte única compartilhada pelos três especialistas (estoque, fornecedores e
transporte). Na F1 apenas compõe o texto final entregue ao usuário — não há
envio externo (e-mail/API), que fica para a F2 com HITL.
"""

from __future__ import annotations

from langchain_core.tools import BaseTool, tool

ROTULO_RESPOSTA = "Resposta logística"
ROTULO_JUSTIFICATIVA = "Justificativa"
ROTULO_FONTES = "Fontes"
FONTES_VAZIAS = "não informadas"

INSTRUCAO_RESPOSTA = (
    "Encerre sempre chamando enviar_resposta_logistica com a resposta, a "
    "justificativa e as fontes (dados/tabelas) usadas. Sem base nos dados, não "
    "invente: deixe as fontes vazias para o sistema sinalizar insuficiência."
)


@tool
def enviar_resposta_logistica(
    resposta: str, fontes: str = "", justificativa: str = ""
) -> str:
    """Compõe a resposta logística final ao usuário (sem envio externo na F1)."""
    texto = resposta.strip()
    if not texto:
        return "Nenhum conteúdo para compor a resposta logística."
    linhas = [f"{ROTULO_RESPOSTA}:", texto]
    motivo = justificativa.strip()
    if motivo:
        linhas.append(f"{ROTULO_JUSTIFICATIVA}: {motivo}")
    linhas.append(f"{ROTULO_FONTES}: {fontes.strip() or FONTES_VAZIAS}")
    return "\n".join(linhas)


NOME_TOOL_RESPOSTA = enviar_resposta_logistica.name
COMMON_TOOLS: list[BaseTool] = [enviar_resposta_logistica]
