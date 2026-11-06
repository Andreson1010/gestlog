"""Casos de uso de conta: onboarding da empresa e convite de usuários."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi_users import exceptions
from fastapi_users.password import PasswordHelper
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from gestlog.db.models import Convite, Empresa, Membership, User

_password_helper = PasswordHelper()


class UltimoAdministradorError(Exception):
    """Erro ao tentar rebaixar/remover o último administrador da empresa."""


class ConviteInvalidoError(Exception):
    """Convite inexistente, expirado ou já utilizado."""


class ConviteDuplicadoError(Exception):
    """Usuário já é membro da empresa convidante."""


async def _por_email(session: AsyncSession, email: str) -> User | None:
    """Busca um usuário pelo e-mail (sem escopo de empresa)."""
    stmt = select(User).where(User.email == email)
    return (await session.execute(stmt)).scalars().first()


def _novo_usuario(email: str, senha: str) -> User:
    """Constrói um usuário ativo e verificado com a senha já hasheada."""
    return User(
        email=email,
        hashed_password=_password_helper.hash(senha),
        is_active=True,
        is_verified=True,
    )


async def criar_conta(
    session: AsyncSession,
    nome_empresa: str,
    email: str,
    senha: str,
) -> tuple[Empresa, User]:
    """Cria empresa e usuário fundador (admin) numa única transação.

    A empresa, o usuário e o vínculo são persistidos no mesmo ``commit`` para
    não deixar usuário órfão se a gravação do vínculo falhar.
    """
    if await _por_email(session, email) is not None:
        raise exceptions.UserAlreadyExists(email)
    empresa = Empresa(nome=nome_empresa)
    usuario = _novo_usuario(email, senha)
    session.add_all([empresa, usuario])
    await session.flush()
    session.add(Membership(user_id=usuario.id, empresa_id=empresa.id, papel="admin"))
    await session.commit()
    return empresa, usuario


def _hash_token(token: str) -> str:
    """SHA-256 hex do token de convite (o token em claro nunca é persistido)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def criar_convite(
    session: AsyncSession,
    empresa_id: UUID,
    email: str,
    papel: str,
    validade_dias: int,
) -> tuple[Convite, str]:
    """Cria um convite pendente e devolve o token em claro (uma única vez).

    O admin não define a senha do convidado (AD-015): quem aceita o convite
    escolhe a própria. O token é devolvido só no retorno desta chamada — a
    entrega por e-mail fica para a integração de notificações.
    """
    usuario = await _por_email(session, email)
    if usuario is not None and await _vinculo_do_usuario(
        session, empresa_id, usuario.id
    ):
        raise ConviteDuplicadoError(email)
    token = secrets.token_urlsafe(32)
    convite = Convite(
        empresa_id=empresa_id,
        email=email,
        papel=papel,
        token_hash=_hash_token(token),
        expira_em=datetime.now(UTC) + timedelta(days=validade_dias),
    )
    session.add(convite)
    await session.commit()
    return convite, token


async def _convite_valido(session: AsyncSession, token: str) -> Convite | None:
    """Busca o convite pelo token, exigindo não usado e dentro da validade."""
    stmt = select(Convite).where(
        Convite.token_hash == _hash_token(token),
        Convite.usado_em.is_(None),
        Convite.expira_em > datetime.now(UTC),
    )
    return (await session.execute(stmt)).scalars().first()


async def aceitar_convite(
    session: AsyncSession, token: str, senha: str
) -> tuple[User, Convite]:
    """Aceita o convite definindo a própria senha e cria o vínculo.

    Para e-mail já cadastrado sem vínculo, vincula e redefine a senha (quem
    tem o token válido do admin pode assumir o acesso convidado). Erros de
    unicidade (dupla aceitação concorrente) sobem ``IntegrityError``.
    """
    convite = await _convite_valido(session, token)
    if convite is None:
        raise ConviteInvalidoError
    usuario = await _por_email(session, convite.email)
    if usuario is None:
        usuario = _novo_usuario(convite.email, senha)
        session.add(usuario)
        await session.flush()
    else:
        usuario.hashed_password = _password_helper.hash(senha)
    session.add(
        Membership(
            user_id=usuario.id, empresa_id=convite.empresa_id, papel=convite.papel
        )
    )
    convite.usado_em = datetime.now(UTC)
    await session.commit()
    return usuario, convite


async def listar_usuarios(
    session: AsyncSession, empresa_id: UUID
) -> list[tuple[Membership, User]]:
    """Lista os vínculos da empresa com o usuário correspondente.

    A junção é feita por ``JOIN`` direto entre ``Membership.user_id`` e
    ``User.id``: as duas colunas usam o tipo ``GUID`` do FastAPI Users, então
    serializam de forma idêntica e a junção resolve em qualquer dialeto.
    """
    stmt = (
        select(Membership, User)
        .join(User, Membership.user_id == User.id)
        .where(Membership.empresa_id == empresa_id)
        .order_by(Membership.created_at, Membership.id)
    )
    linhas = (await session.execute(stmt)).all()
    return [(vinculo, usuario) for vinculo, usuario in linhas]


async def listar_vinculos(session: AsyncSession, user_id: UUID) -> list[Membership]:
    """Lista os vínculos do usuário (mais antigo primeiro), com a empresa carregada."""
    stmt = (
        select(Membership)
        .options(selectinload(Membership.empresa))
        .where(Membership.user_id == user_id)
        .order_by(Membership.created_at, Membership.id)
    )
    return list((await session.execute(stmt)).scalars().all())


async def vinculo_na_empresa(
    session: AsyncSession, user_id: UUID, empresa_id: UUID
) -> Membership | None:
    """Busca o vínculo do usuário em uma empresa específica."""
    stmt = select(Membership).where(
        Membership.user_id == user_id,
        Membership.empresa_id == empresa_id,
    )
    return (await session.execute(stmt)).scalars().first()


async def _vinculo_do_usuario(
    session: AsyncSession, empresa_id: UUID, user_id: UUID
) -> Membership | None:
    """Busca o vínculo de um usuário na empresa (sem vazar outra empresa)."""
    stmt = select(Membership).where(
        Membership.empresa_id == empresa_id,
        Membership.user_id == user_id,
    )
    return (await session.execute(stmt)).scalars().first()


async def _contar_admins(session: AsyncSession, empresa_id: UUID) -> int:
    """Conta os administradores da empresa."""
    stmt = (
        select(func.count())
        .select_from(Membership)
        .where(Membership.empresa_id == empresa_id, Membership.papel == "admin")
    )
    return int((await session.execute(stmt)).scalar_one())


async def _exigir_nao_ultimo_admin(session: AsyncSession, vinculo: Membership) -> None:
    """Impede rebaixar/remover o único administrador da empresa.

    A empresa sem administrador ficaria incapaz de gerenciar usuários, então a
    operação é barrada com ``UltimoAdministradorError``.
    """
    if vinculo.papel != "admin":
        return
    if await _contar_admins(session, vinculo.empresa_id) <= 1:
        raise UltimoAdministradorError(str(vinculo.user_id))


async def alterar_papel(
    session: AsyncSession, empresa_id: UUID, user_id: UUID, papel: str
) -> Membership | None:
    """Altera o papel do usuário na empresa; ``None`` se o vínculo não existir.

    Impede rebaixar o último administrador, para não deixar a empresa sem quem
    gerencie usuários.
    """
    vinculo = await _vinculo_do_usuario(session, empresa_id, user_id)
    if vinculo is None:
        return None
    if papel != "admin":
        await _exigir_nao_ultimo_admin(session, vinculo)
    vinculo.papel = papel
    await session.commit()
    return vinculo


async def remover_usuario(
    session: AsyncSession, empresa_id: UUID, user_id: UUID
) -> bool:
    """Remove o vínculo do usuário com a empresa, revogando o acesso.

    Devolve ``False`` quando o vínculo não existe; impede remover o último
    administrador.
    """
    vinculo = await _vinculo_do_usuario(session, empresa_id, user_id)
    if vinculo is None:
        return False
    await _exigir_nao_ultimo_admin(session, vinculo)
    await session.delete(vinculo)
    await session.commit()
    return True
