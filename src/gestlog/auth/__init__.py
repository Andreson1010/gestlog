"""Autenticação e tenancy do gestlog."""

from __future__ import annotations

from gestlog.auth.backend import build_auth_backend
from gestlog.auth.db import get_async_engine, get_async_session, get_user_db
from gestlog.auth.manager import UserManager, get_user_manager
from gestlog.auth.routes import create_auth_router

__all__ = [
    "UserManager",
    "build_auth_backend",
    "create_auth_router",
    "get_async_engine",
    "get_async_session",
    "get_user_db",
    "get_user_manager",
]
