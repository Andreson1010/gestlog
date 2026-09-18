"""Catálogo de eventos de auditoria e registro por empresa."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from gestlog.db.models import AuditLog
from gestlog.repositories.telemetry import AuditRepository

EVENTO_PERGUNTA = "pergunta"
EVENTO_RECOMENDACAO = "recomendacao"
EVENTO_FEEDBACK = "feedback"
EVENTO_IMPORTACAO = "importacao"

EVENTOS: tuple[str, ...] = (
    EVENTO_PERGUNTA,
    EVENTO_RECOMENDACAO,
    EVENTO_FEEDBACK,
    EVENTO_IMPORTACAO,
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
