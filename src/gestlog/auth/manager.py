"""Gerenciador de usuários do FastAPI Users."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users_db_sqlalchemy import SQLAlchemyUserDatabase

from gestlog.auth.db import get_user_db
from gestlog.config import Settings, get_settings
from gestlog.db.models import User


class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    """Cadastro e autenticação de usuários, com segredos da configuração."""

    def __init__(self, user_db: SQLAlchemyUserDatabase, settings: Settings) -> None:
        super().__init__(user_db)
        self.reset_password_token_secret = settings.auth_secret
        self.verification_token_secret = settings.auth_secret


async def get_user_manager(
    user_db: Annotated[SQLAlchemyUserDatabase, Depends(get_user_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncIterator[UserManager]:
    """Fornece o gerenciador de usuários por requisição."""
    yield UserManager(user_db, settings)
