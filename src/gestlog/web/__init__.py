"""Camada web (apps) do gestlog."""

from __future__ import annotations

from gestlog.web.onboarding import create_onboarding_router
from gestlog.web.schemas import ContaCreate, ConviteCreate

__all__ = ["ContaCreate", "ConviteCreate", "create_onboarding_router"]
