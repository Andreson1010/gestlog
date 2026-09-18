"""Casos de uso de conta: onboarding da empresa e convite de usuários."""

from __future__ import annotations

from uuid import UUID

from fastapi_users import exceptions
from fastapi_users.password import PasswordHelper
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from gestlog.db.models import Empresa, Membership, User

_password_helper = PasswordHelper()


class UltimoAdministradorError(Exception):
    """Erro ao tentar rebaixar/remover o último administrador da empresa."""


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


async def convidar_usuario(
    session: AsyncSession,
    empresa_id: UUID,
    email: str,
    papel: str,
    senha: str,
) -> Membership:
    """Vincula um usuário à empresa, criando-o numa única transação se preciso."""
    usuario = await _por_email(session, email)
    if usuario is None:
        usuario = _novo_usuario(email, senha)
        session.add(usuario)
        await session.flush()
    vinculo = Membership(user_id=usuario.id, empresa_id=empresa_id, papel=papel)
    session.add(vinculo)
    await session.commit()
    return vinculo


async def listar_usuarios(
    session: AsyncSession, empresa_id: UUID
) -> list[tuple[Membership, User]]:
    """Lista os vínculos da empresa com o usuário correspondente.

    A busca dos usuários é feita por ``IN`` (não por JOIN): ``Membership.user_id``
    usa ``Uuid`` e ``User.id`` usa o ``GUID`` do FastAPI Users, que serializam de
    formas diferentes no SQLite e quebrariam a junção direta.
    """
    stmt = (
        select(Membership)
        .where(Membership.empresa_id == empresa_id)
        .order_by(Membership.created_at, Membership.id)
    )
    vinculos = list((await session.execute(stmt)).scalars().all())
    if not vinculos:
        return []
    ids = [vinculo.user_id for vinculo in vinculos]
    usuarios = (await session.execute(select(User).where(User.id.in_(ids)))).scalars()
    por_id = {usuario.id: usuario for usuario in usuarios.all()}
    return [
        (vinculo, por_id[vinculo.user_id])
        for vinculo in vinculos
        if vinculo.user_id in por_id
    ]


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
