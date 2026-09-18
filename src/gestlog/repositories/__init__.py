"""Repositórios com escopo de empresa do gestlog."""

from __future__ import annotations

from gestlog.repositories.base import EmpresaScopedRepository
from gestlog.repositories.catalog import (
    StockRepository,
    SupplierRepository,
    TransportRepository,
)
from gestlog.repositories.conversations import (
    ConversationRepository,
    FeedbackRepository,
    MessageRepository,
    RecommendationRepository,
)
from gestlog.repositories.empresas import EmpresaRepository, MembershipRepository
from gestlog.repositories.imports import ImportJobRepository
from gestlog.repositories.kpis import KpiRepository, ResumoKpis
from gestlog.repositories.telemetry import AuditRepository, UsageRepository

__all__ = [
    "EmpresaScopedRepository",
    "StockRepository",
    "SupplierRepository",
    "TransportRepository",
    "ConversationRepository",
    "FeedbackRepository",
    "MessageRepository",
    "RecommendationRepository",
    "ImportJobRepository",
    "KpiRepository",
    "ResumoKpis",
    "AuditRepository",
    "UsageRepository",
    "MembershipRepository",
    "EmpresaRepository",
]
