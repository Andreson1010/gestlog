"""Router de autenticação (login/logout por cookie)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from fastapi_users import FastAPIUsers

from gestlog.auth.backend import build_auth_backend
from gestlog.auth.manager import get_user_manager
from gestlog.config import Settings
from gestlog.db.models import User


def create_auth_router(settings: Settings) -> APIRouter:
    """Cria o router com as rotas ``/login`` e ``/logout`` por cookie."""
    backend = build_auth_backend(settings)
    fastapi_users = FastAPIUsers[User, UUID](get_user_manager, [backend])
    return fastapi_users.get_auth_router(backend)
