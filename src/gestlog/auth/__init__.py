"""Autenticação e tenancy do gestlog."""

from __future__ import annotations

from gestlog.auth.backend import build_auth_backend, get_jwt_strategy
from gestlog.auth.db import get_async_engine, get_async_session, get_user_db
from gestlog.auth.deps import (
    current_active_user,
    current_active_user_optional,
    exigir_papel,
    get_current_empresa,
    get_current_empresa_optional,
    get_current_membership,
    get_current_user,
    verificar_empresa_do_recurso,
)
from gestlog.auth.manager import UserManager, get_user_manager
from gestlog.auth.routes import create_auth_router

__all__ = [
    "UserManager",
    "build_auth_backend",
    "create_auth_router",
    "current_active_user",
    "current_active_user_optional",
    "exigir_papel",
    "get_async_engine",
    "get_async_session",
    "get_current_empresa",
    "get_current_empresa_optional",
    "get_current_membership",
    "get_current_user",
    "get_jwt_strategy",
    "get_user_db",
    "get_user_manager",
    "verificar_empresa_do_recurso",
]
