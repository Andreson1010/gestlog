"""Ferramenta comum de composição da resposta logística.

Fonte única compartilhada pelos três especialistas (estoque, fornecedores e
transporte). Na F1 apenas compõe o texto final entregue ao usuário — não há
envio externo (e-mail/API), que fica para a F2 com HITL.
"""

from __future__ import annotations

from langchain_core.tools import BaseTool, tool

_ROTULO = "Resposta logística"
_FONTES_VAZIAS = "não informadas"


@tool
def enviar_resposta_logistica(resposta: str, fontes: str = "") -> str:
    """Compõe a resposta logística final ao usuário (sem envio externo na F1)."""
    texto = resposta.strip()
    if not texto:
        return "Nenhum conteúdo para compor a resposta logística."
    referencia = fontes.strip() or _FONTES_VAZIAS
    return f"{_ROTULO}:\n{texto}\nFontes: {referencia}"


COMMON_TOOLS: list[BaseTool] = [enviar_resposta_logistica]
