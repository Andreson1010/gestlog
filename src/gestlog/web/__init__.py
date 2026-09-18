"""Camada web (apps) do gestlog."""

from __future__ import annotations

from gestlog.web.app import create_app
from gestlog.web.chat import create_chat_router, get_chat_model
from gestlog.web.ingestion_ui import create_ingestion_router, get_sync_session
from gestlog.web.kpis import create_kpis_router
from gestlog.web.onboarding import create_onboarding_router
from gestlog.web.schemas import ContaCreate, ConviteCreate

__all__ = [
    "ContaCreate",
    "ConviteCreate",
    "create_app",
    "create_chat_router",
    "create_ingestion_router",
    "create_kpis_router",
    "create_onboarding_router",
    "get_chat_model",
    "get_sync_session",
]
