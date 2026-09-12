"""Backend de autenticação por cookie + JWT."""

from __future__ import annotations

from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
    JWTStrategy,
)

from gestlog.config import Settings


def build_auth_backend(settings: Settings) -> AuthenticationBackend:
    """Monta o backend de auth (cookie + JWT) a partir da configuração."""
    transport = CookieTransport(
        cookie_name=settings.auth_cookie_name,
        cookie_max_age=settings.session_expire_minutes * 60,
        cookie_secure=settings.auth_cookie_secure,
        cookie_samesite="lax",
    )

    def get_jwt_strategy() -> JWTStrategy:
        return JWTStrategy(
            secret=settings.auth_secret,
            lifetime_seconds=settings.session_expire_minutes * 60,
        )

    return AuthenticationBackend(
        name="cookie",
        transport=transport,
        get_strategy=get_jwt_strategy,
    )
