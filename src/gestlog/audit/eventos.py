"""Catálogo de eventos de auditoria e registro por empresa.

Eventos de correção (F2/HITL) e seus call sites em ``correcoes.servico``:

- ``EVENTO_CORRECAO_APROVADA`` (``aprovar``, após validar o item):
  ``{item_id, tipo, alvo_chave, campo}``.
- ``EVENTO_CORRECAO_REJEITADA`` (``rejeitar``):
  ``{item_id, tipo, alvo_chave, campo}``.
- ``EVENTO_CORRECAO_APLICADA`` (``aprovar``, após o ``upsert``):
  ``{item_id, tipo, alvo_chave, campo, valor}``.
- ``EVENTO_CORRECAO_FALHOU`` (``aprovar``, conflito/alvo/erro):
  ``{item_id, motivo}``.

O ``detalhe`` **nunca** carrega ``justificativa``/``motivo_rejeicao`` (texto livre do
usuário) nem PII. O ``valor`` é dado operacional de catálogo, truncado, e o ``motivo``
de ``EVENTO_CORRECAO_FALHOU`` é um código de falha, não texto livre do usuário. O valor
aplicado completo fica no ``ItemCorrecao``, referenciável por ``item_id``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from gestlog.db.models import AuditLog
from gestlog.repositories.telemetry import AuditRepository

EVENTO_PERGUNTA = "pergunta"
EVENTO_RECOMENDACAO = "recomendacao"
EVENTO_FEEDBACK = "feedback"
EVENTO_IMPORTACAO = "importacao"

EVENTO_CORRECAO_APROVADA = "correcao_aprovada"
EVENTO_CORRECAO_REJEITADA = "correcao_rejeitada"
EVENTO_CORRECAO_APLICADA = "correcao_aplicada"
EVENTO_CORRECAO_FALHOU = "correcao_falhou"

EVENTOS: tuple[str, ...] = (
    EVENTO_PERGUNTA,
    EVENTO_RECOMENDACAO,
    EVENTO_FEEDBACK,
    EVENTO_IMPORTACAO,
    EVENTO_CORRECAO_APROVADA,
    EVENTO_CORRECAO_REJEITADA,
    EVENTO_CORRECAO_APLICADA,
    EVENTO_CORRECAO_FALHOU,
)


def registrar_evento(
    session: Session,
    empresa_id: UUID,
    evento: str,
    user_id: UUID | None = None,
    detalhe: dict | None = None,
) -> AuditLog:
    """Registra um evento de auditoria por empresa, sem confirmar a transação.

    O commit fica com quem controla a unidade de trabalho, para que o evento
    entre na mesma transação da interação auditada. O catálogo de ``evento`` é
    validado na entrada; o ``detalhe`` nunca deve carregar o valor sensível
    (apenas metadados como domínio, fontes e categorias redigidas).
    """
    if evento not in EVENTOS:
        raise ValueError(f"Evento de auditoria desconhecido: {evento}")
    return AuditRepository(session).record(empresa_id, evento, user_id, detalhe)
