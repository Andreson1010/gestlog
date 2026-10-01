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
from gestlog.repositories.correcoes import CorrectionRepository
from gestlog.repositories.empresas import EmpresaRepository, MembershipRepository
from gestlog.repositories.historico import HistoricoRepository
from gestlog.repositories.imports import ImportJobRepository
from gestlog.repositories.kpis import KpiRepository, ResumoKpis
from gestlog.repositories.relatorios import (
    Fornecedor,
    ItemEstoque,
    RegistroTransporte,
    RelatorioRepository,
    ResumoEstoque,
    ResumoFornecedores,
    ResumoTransporte,
)
from gestlog.repositories.telemetry import AuditRepository, UsageRepository
from gestlog.repositories.users import UserRepository

__all__ = [
    "EmpresaScopedRepository",
    "StockRepository",
    "SupplierRepository",
    "TransportRepository",
    "ConversationRepository",
    "FeedbackRepository",
    "MessageRepository",
    "RecommendationRepository",
    "CorrectionRepository",
    "HistoricoRepository",
    "ImportJobRepository",
    "KpiRepository",
    "ResumoKpis",
    "RelatorioRepository",
    "ItemEstoque",
    "ResumoEstoque",
    "RegistroTransporte",
    "ResumoTransporte",
    "Fornecedor",
    "ResumoFornecedores",
    "AuditRepository",
    "UsageRepository",
    "MembershipRepository",
    "EmpresaRepository",
    "UserRepository",
]
