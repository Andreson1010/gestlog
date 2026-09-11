"""Repositórios com escopo de tenant do gestlog."""

from __future__ import annotations

from gestlog.repositories.base import TenantScopedRepository
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
from gestlog.repositories.imports import ImportJobRepository
from gestlog.repositories.telemetry import AuditRepository, UsageRepository
from gestlog.repositories.tenants import MembershipRepository, TenantRepository

__all__ = [
    "TenantScopedRepository",
    "StockRepository",
    "SupplierRepository",
    "TransportRepository",
    "ConversationRepository",
    "FeedbackRepository",
    "MessageRepository",
    "RecommendationRepository",
    "ImportJobRepository",
    "AuditRepository",
    "UsageRepository",
    "MembershipRepository",
    "TenantRepository",
]
