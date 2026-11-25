"""Testes dos casos de uso de conta: cadastro, convite e identidade (T2)."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi_users import exceptions
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from gestlog.auth import accounts
from gestlog.auth.accounts import (
    ConviteDuplicadoError,
    ConviteEmailRegistradoError,
    aceitar_convite,
    criar_conta,
    criar_convite,
)
from gestlog.config import Settings
from gestlog.db.models import Convite, User
from gestlog.db.session import (
    build_async_engine,
    build_async_session_factory,
    init_async_db,
)

_SENHA = "senha-secreta-123"


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        database_url="sqlite+aiosqlite:///:memory:",
        auth_secret="segredo-de-teste-com-pelo-menos-32-bytes",
        auth_cookie_secure=False,
    )


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    motor = build_async_engine(_settings())
    await init_async_db(motor)
    yield motor
    await motor.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    factory = build_async_session_factory(engine)
    async with factory() as sessao:
        yield sessao


async def _usuario_por_email(engine: AsyncEngine, email: str) -> User | None:
    """Lê o usuário pelo e-mail exato como está no banco (fora do caso de uso)."""
    factory = build_async_session_factory(engine)
    async with factory() as sessao:
        stmt = select(User).where(User.email == email)
        return (await sessao.execute(stmt)).scalars().first()


async def _convite_gravado(engine: AsyncEngine) -> Convite | None:
    """Lê o único convite do banco (fora do caso de uso)."""
    factory = build_async_session_factory(engine)
    async with factory() as sessao:
        return (await sessao.execute(select(Convite))).scalars().first()


def test_normalizar_email_cobre_espacos_e_caixa() -> None:
    """O e-mail canônico é o strip + casefold da entrada."""
    assert accounts.normalizar_email("  Ana@X.COM  ") == "ana@x.com"


async def test_email_persistido_normalizado(
    session: AsyncSession, engine: AsyncEngine
) -> None:
    """Cadastro com caixa/espaços divergentes grava o e-mail canônico (IDT-01)."""
    _, usuario = await criar_conta(session, "Empresa A", "  Ana@X.COM ", _SENHA)

    assert usuario.email == "ana@x.com"
    gravado = await _usuario_por_email(engine, "ana@x.com")
    assert gravado is not None
    assert gravado.email == "ana@x.com"


async def test_email_normalizado_recusa_duplicata_por_caixa_ou_espaco(
    session: AsyncSession,
) -> None:
    """'Ana@X.COM ' e 'ana@x.com' disputam a mesma identidade (IDT-01/I-1)."""
    await criar_conta(session, "Empresa A", "ana@x.com", _SENHA)

    with pytest.raises(exceptions.UserAlreadyExists):
        await criar_conta(session, "Outra", "Ana@X.COM ", _SENHA)


async def test_convite_para_email_divergente_em_caixa_e_recusado(
    session: AsyncSession,
) -> None:
    """Convidar e-mail registrado em caixa diversa não passa (IDT-01)."""
    empresa, _ = await criar_conta(session, "Empresa A", "ana@x.com", _SENHA)

    with pytest.raises(ConviteDuplicadoError):
        await criar_convite(
            session, empresa.id, "  ANA@X.com ", "operador", validade_dias=1
        )


async def test_convite_persiste_email_normalizado(
    session: AsyncSession, engine: AsyncEngine
) -> None:
    """O convite grava o e-mail canônico, não o digitado (IDT-01)."""
    empresa, _ = await criar_conta(session, "Empresa A", "admin@empresa.com", _SENHA)

    _, token = await criar_convite(
        session, empresa.id, "  Operador@Empresa.COM ", "operador", validade_dias=1
    )
    assert token

    gravado = await _convite_gravado(engine)
    assert gravado is not None
    assert gravado.email == "operador@empresa.com"


async def test_conta_nasce_is_verified_false(session: AsyncSession) -> None:
    """Conta nasce não verificada no cadastro e no aceite de convite (IDT-05)."""
    empresa, admin = await criar_conta(
        session, "Empresa A", "admin@empresa.com", _SENHA
    )
    assert admin.is_verified is False

    _, token = await criar_convite(
        session, empresa.id, "operador@empresa.com", "operador", validade_dias=1
    )
    convidado, _ = await aceitar_convite(session, token, _SENHA)

    assert convidado.is_verified is False


async def test_aceite_de_email_registrado_continua_recusando(
    session: AsyncSession, engine: AsyncEngine
) -> None:
    """Guard do takeover (L-048/AD-015) intacto: aceite não altera credencial (EDG-08)."""
    empresa, admin = await criar_conta(
        session, "Empresa A", "admin@empresa.com", _SENHA
    )
    senha_original = admin.hashed_password
    session.add(
        Convite(
            empresa_id=UUID(str(empresa.id)),
            email="admin@empresa.com",
            papel="operador",
            token_hash=hashlib.sha256(b"token-forjado").hexdigest(),
            expira_em=datetime.now(UTC) + timedelta(days=1),
        )
    )
    await session.commit()

    with pytest.raises(ConviteEmailRegistradoError):
        await aceitar_convite(session, "token-forjado", "senha-do-atacante-999")

    gravado = await _usuario_por_email(engine, "admin@empresa.com")
    assert gravado is not None
    assert gravado.hashed_password == senha_original
