"""Suporte dos testes de aceitação dos relatórios operacionais.

Reúne constantes e helpers usados pelos arquivos ``test_relatorios_*.py``.
Não é coletado pelo pytest (sem prefixo ``test_``).
"""

from __future__ import annotations

import contextlib
import csv
import io
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

from fastapi_users.password import PasswordHelper
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import Session, sessionmaker

from gestlog.db.models import CatalogoHistorico, Membership, User
from gestlog.db.session import build_async_session_factory
from gestlog.ingestion import importar

SENHA = "senha-secreta-123"
COOKIE = "gestlog_auth"
DOMINIOS = ("estoque", "transporte", "fornecedores")

QUANDO = datetime(2026, 6, 10, 12, tzinfo=UTC)
JANEIRO = datetime(2026, 1, 10, 12, tzinfo=UTC)


@contextlib.contextmanager
def sessao(fabrica: sessionmaker[Session]) -> Iterator[Session]:
    """Abre uma sessão do fabricante e a fecha ao sair."""
    with fabrica() as session:
        yield session


async def criar_conta(client: AsyncClient, empresa: str, email: str) -> dict[str, str]:
    """Cria a conta (empresa + admin) via onboarding e devolve os ids."""
    resposta = await client.post(
        "/onboarding",
        json={"nome_empresa": empresa, "email": email, "senha": SENHA},
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


async def login(client: AsyncClient, email: str) -> None:
    """Autentica a sessão no cookie do cliente."""
    resposta = await client.post(
        "/auth/login", data={"username": email, "password": SENHA}
    )
    assert resposta.status_code == 204, resposta.text
    assert client.cookies.get(COOKIE)


async def convidar(client: AsyncClient, email: str, papel: str = "operador") -> None:
    """Convida um usuário para o tenant da sessão (exige admin autenticado)."""
    resposta = await client.post(
        "/empresa/convites",
        json={"email": email, "papel": papel, "senha": SENHA},
    )
    assert resposta.status_code == 201, resposta.text


async def criar_usuario(
    motor_async: AsyncEngine,
    empresa_id: UUID,
    email: str,
    papel: str = "admin",
) -> UUID:
    """Cria um usuário vinculado à empresa com o papel informado."""
    factory = build_async_session_factory(motor_async)
    async with factory() as session:
        usuario = User(
            email=email,
            hashed_password=PasswordHelper().hash(SENHA),
            is_active=True,
            is_verified=True,
        )
        session.add(usuario)
        await session.flush()
        session.add(Membership(user_id=usuario.id, empresa_id=empresa_id, papel=papel))
        await session.commit()
        return usuario.id


def semear(
    fabrica: sessionmaker[Session],
    empresa_id: UUID,
    dominio: str,
    chave: str,
    importado_em: datetime = QUANDO,
    **payload: object,
) -> None:
    """Insere um snapshot de catálogo com o timestamp e payload informados."""
    with sessao(fabrica) as session:
        session.add(
            CatalogoHistorico(
                empresa_id=empresa_id,
                dominio=dominio,
                chave=chave,
                importado_em=importado_em,
                **payload,
            )
        )
        session.commit()


def importar_arquivo(
    fabrica: sessionmaker[Session],
    empresa_id: UUID,
    tipo: str,
    texto: str,
    nome: str = "dados.csv",
) -> int:
    """Executa a importação real de um texto CSV e devolve as linhas aceitas."""
    with sessao(fabrica) as session:
        job = importar(session, empresa_id, tipo, texto.encode("utf-8"), nome)
        session.commit()
        return job.aceitas


def ler_csv(dados: bytes) -> list[list[str]]:
    """Parseia um CSV de relatório (separador ``;``, BOM tolerado)."""
    return list(csv.reader(io.StringIO(dados.decode("utf-8-sig")), delimiter=";"))


def celulas_da_linha(html: str, chave: str) -> list[str]:
    """Devolve o texto das células ``<td>`` da linha cujo 1º campo é ``chave``."""
    for linha in re.findall(r"<tr>(.*?)</tr>", html, flags=re.S):
        celulas = [
            re.sub(r"<[^>]+>", "", celula).strip()
            for celula in re.findall(r"<td>(.*?)</td>", linha, flags=re.S)
        ]
        if celulas and celulas[0] == chave:
            return celulas
    return []


async def exportar(
    client: AsyncClient,
    dominio: str,
    params: dict[str, str] | None = None,
) -> bytes:
    """Solicita a exportação CSV do domínio e devolve o corpo."""
    resposta = await client.get(f"/relatorios/{dominio}/exportar", params=params or {})
    assert resposta.status_code == 200, resposta.text
    return resposta.content
