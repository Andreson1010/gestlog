"""Modelos ORM do gestlog.

Todas as tabelas de dados carregam ``empresa_id`` para garantir o isolamento
entre empresas-clientes. O modelo ``User`` estende a base do FastAPI Users.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gestlog.db.base import Base

Papel = Literal["admin", "operador", "gestor"]
StatusImport = Literal["processando", "concluido", "falhou"]
Decisao = Literal["aceita", "descartada"]


def _agora() -> datetime:
    return datetime.now(UTC)


class Empresa(Base):
    """Empresa-cliente (empresa) do SaaS."""

    __tablename__ = "empresa"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    nome: Mapped[str] = mapped_column(String(120))
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )

    members: Mapped[list[Membership]] = relationship(
        back_populates="empresa", cascade="all, delete-orphan"
    )


class User(SQLAlchemyBaseUserTableUUID, Base):
    """Usuário autenticável (base do FastAPI Users)."""

    __tablename__ = "user"


class Membership(Base):
    """Vínculo de um usuário a um empresa, com papel."""

    __tablename__ = "membership"
    __table_args__ = (UniqueConstraint("user_id", "empresa_id", name="uq_membership"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("user.id"))
    empresa_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("empresa.id"))
    papel: Mapped[str] = mapped_column(String(20), default="operador")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )

    empresa: Mapped[Empresa] = relationship(back_populates="members")


class ImportJob(Base):
    """Execução de importação de um conjunto de dados."""

    __tablename__ = "import_job"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    empresa_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("empresa.id"))
    tipo: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="processando")
    aceitas: Mapped[int] = mapped_column(Integer, default=0)
    rejeitadas: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )

    errors: Mapped[list[ImportError]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class ImportError(Base):
    """Erro de validação em uma linha importada."""

    __tablename__ = "import_error"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    import_job_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("import_job.id"))
    linha: Mapped[int] = mapped_column(Integer)
    motivo: Mapped[str] = mapped_column(String(255))

    job: Mapped[ImportJob] = relationship(back_populates="errors")


class StockItem(Base):
    """Item de estoque de um empresa."""

    __tablename__ = "stock_item"
    __table_args__ = (
        UniqueConstraint("empresa_id", "sku", name="uq_stock_empresa_sku"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    empresa_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("empresa.id"))
    sku: Mapped[str] = mapped_column(String(40))
    nome: Mapped[str] = mapped_column(String(120))
    quantidade: Mapped[int] = mapped_column(Integer, default=0)
    minimo: Mapped[int] = mapped_column(Integer, default=0)
    local: Mapped[str] = mapped_column(String(40), default="")


class Supplier(Base):
    """Fornecedor de um empresa."""

    __tablename__ = "supplier"
    __table_args__ = (
        UniqueConstraint("empresa_id", "fornecedor_id", name="uq_supplier_empresa"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    empresa_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("empresa.id"))
    fornecedor_id: Mapped[str] = mapped_column(String(40))
    nome: Mapped[str] = mapped_column(String(120))
    categoria: Mapped[str] = mapped_column(String(60), default="")
    prazo_dias: Mapped[int] = mapped_column(Integer, default=0)
    avaliacao: Mapped[float] = mapped_column(Float, default=0.0)
    ativo: Mapped[bool] = mapped_column(default=True)


class TransportRecord(Base):
    """Registro de transporte/frete/rastreio de um empresa."""

    __tablename__ = "transport_record"
    __table_args__ = (
        UniqueConstraint("empresa_id", "codigo_rastreio", name="uq_transport_empresa"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    empresa_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("empresa.id"))
    codigo_rastreio: Mapped[str] = mapped_column(String(40))
    origem: Mapped[str] = mapped_column(String(80), default="")
    destino: Mapped[str] = mapped_column(String(80), default="")
    peso_kg: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(120), default="")


class Conversation(Base):
    """Conversa de um usuário dentro de um empresa."""

    __tablename__ = "conversation"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    empresa_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("empresa.id"))
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )


class Message(Base):
    """Mensagem de uma conversa (conteúdo já redigido)."""

    __tablename__ = "message"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("conversation.id"))
    papel: Mapped[str] = mapped_column(String(20))
    conteudo_redigido: Mapped[str] = mapped_column(String(4000), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )


class Recommendation(Base):
    """Recomendação gerada pelo copiloto, com justificativa e fontes."""

    __tablename__ = "recommendation"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("conversation.id"))
    dominio: Mapped[str] = mapped_column(String(30))
    texto: Mapped[str] = mapped_column(String(4000))
    justificativa: Mapped[str] = mapped_column(String(2000), default="")
    fontes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )


class Feedback(Base):
    """Aceite ou descarte de uma recomendação pelo operador."""

    __tablename__ = "feedback"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    recommendation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("recommendation.id")
    )
    decisao: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )


class UsageRecord(Base):
    """Consumo de LLM atribuído a um empresa."""

    __tablename__ = "usage_record"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    empresa_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("empresa.id"))
    modelo: Mapped[str] = mapped_column(String(80))
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )


class AuditLog(Base):
    """Evento de auditoria por empresa."""

    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    empresa_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("empresa.id"))
    user_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("user.id"), nullable=True
    )
    evento: Mapped[str] = mapped_column(String(60))
    detalhe: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_agora
    )
