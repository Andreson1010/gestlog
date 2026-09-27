"""Suporte compartilhado dos testes de aceitação da F2 (HITL).

Reúne constantes e helpers usados pelos arquivos `test_f2_hitl*.py`. Não é
coletado pelo pytest (sem prefixo `test_`).
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from datetime import datetime
from uuid import UUID

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from gestlog.correcoes import CorrectionService
from gestlog.db.models import AuditLog, Empresa, ItemCorrecao, StockItem
from gestlog.repositories.catalog import StockRepository
from gestlog.web import get_chat_model

SENHA = "senha-secreta-123"
COOKIE = "gestlog_auth"
HISTORICO = "/correcoes/historico"

TOOLS_ESTOQUE = {
    "consultar_estoque",
    "calcular_reposicao",
    "listar_movimentacoes",
    "enviar_resposta_logistica",
}
TOOLS_TRANSPORTE = {
    "calcular_frete",
    "consultar_prazo",
    "rastrear_entrega",
    "enviar_resposta_logistica",
}
TOOLS_FORNECEDORES = {
    "listar_fornecedores",
    "consultar_fornecedor",
    "avaliar_desempenho",
    "enviar_resposta_logistica",
}


@contextlib.contextmanager
def sessao(fabrica: sessionmaker[Session]) -> Iterator[Session]:
    """Abre uma sessão do fabricante e a fecha ao sair."""
    with fabrica() as session:
        yield session


def usar_modelo(app: FastAPI, model: object) -> None:
    """Injeta o modelo fake na dependência de chat do app."""
    app.dependency_overrides[get_chat_model] = lambda: model


def tool_comum(resposta: str, fontes: str = "estoque") -> list[dict[str, object]]:
    """Tool call da resposta logística comum aos especialistas."""
    return [
        {
            "name": "enviar_resposta_logistica",
            "args": {"resposta": resposta, "fontes": fontes},
            "id": "call-1",
            "type": "tool_call",
        }
    ]


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


def criar_empresa(fabrica: sessionmaker[Session], nome: str = "A") -> UUID:
    """Cria uma empresa direto no banco e devolve o id."""
    with sessao(fabrica) as session:
        empresa = Empresa(nome=nome)
        session.add(empresa)
        session.commit()
        return empresa.id


def semear_estoque(
    fabrica: sessionmaker[Session],
    empresa_id: UUID,
    sku: str,
    *,
    nome: str = "Caixa",
    quantidade: int = 1,
    minimo: int = 2,
    local: str = "",
) -> None:
    """Insere/atualiza um item de estoque do tenant."""
    with sessao(fabrica) as session:
        StockRepository(session).upsert(
            empresa_id, sku, nome, quantidade, minimo, local
        )
        session.commit()


def ler_estoque(
    fabrica: sessionmaker[Session], empresa_id: UUID, sku: str
) -> StockItem:
    """Lê um item de estoque destacado da sessão."""
    with sessao(fabrica) as session:
        item = session.execute(
            select(StockItem).where(
                StockItem.empresa_id == empresa_id, StockItem.sku == sku
            )
        ).scalar_one()
        session.expunge(item)
        return item


def gerar_fila(fabrica: sessionmaker[Session], empresa_id: UUID) -> None:
    """Materializa a fila de correções do tenant."""
    with sessao(fabrica) as session:
        CorrectionService(session, empresa_id).gerar_fila()


def item_correcao(
    fabrica: sessionmaker[Session],
    empresa_id: UUID,
    sku: str,
    campo: str = "local",
    status: str = "pendente",
) -> ItemCorrecao:
    """Busca um item da fila pelo alvo, campo e status, destacado da sessão."""
    with sessao(fabrica) as session:
        stmt = select(ItemCorrecao).where(
            ItemCorrecao.empresa_id == empresa_id,
            ItemCorrecao.alvo_chave == sku,
            ItemCorrecao.campo == campo,
            ItemCorrecao.status == status,
        )
        item = session.execute(stmt).scalar_one()
        session.expunge(item)
        return item


def campos_pendentes(
    fabrica: sessionmaker[Session], empresa_id: UUID, sku: str
) -> set[str]:
    """Campos ainda pendentes de decisão para o alvo informado."""
    with sessao(fabrica) as session:
        stmt = select(ItemCorrecao.campo).where(
            ItemCorrecao.empresa_id == empresa_id,
            ItemCorrecao.alvo_chave == sku,
            ItemCorrecao.status == "pendente",
        )
        return set(session.execute(stmt).scalars().all())


def definir_decidido_em(
    fabrica: sessionmaker[Session], item_id: UUID, quando: datetime
) -> None:
    """Ajusta o timestamp de decisão do item (para testes de período)."""
    with sessao(fabrica) as session:
        item = session.get(ItemCorrecao, item_id)
        assert item is not None
        item.decidido_em = quando
        session.commit()


def eventos_auditoria(
    fabrica: sessionmaker[Session], empresa_id: UUID
) -> list[AuditLog]:
    """Lista os eventos de auditoria do tenant."""
    with sessao(fabrica) as session:
        stmt = select(AuditLog).where(AuditLog.empresa_id == empresa_id)
        return list(session.execute(stmt).scalars().all())


async def aprovar_http(
    client: AsyncClient,
    fabrica: sessionmaker[Session],
    empresa_id: UUID,
    sku: str,
    campo: str = "local",
) -> UUID:
    """Materializa a fila, aprova o item do alvo/campo pela web e devolve o id."""
    await client.get("/correcoes")
    item = item_correcao(fabrica, empresa_id, sku, campo)
    resposta = await client.post(
        f"/correcoes/{item.id}/decisao",
        data={"decisao": "aprovar"},
        follow_redirects=False,
    )
    assert resposta.status_code == 303, resposta.text
    return item.id
