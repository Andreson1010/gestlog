"""Rotas HTML da fila de correções, decisão e trilha (HITL)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, get_args
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from gestlog.auth import exigir_papel, get_current_user
from gestlog.correcoes import (
    PAPEIS_APROVADORES,
    CorrecaoAlvoInvalido,
    CorrecaoNaoAprovavel,
    CorrecaoNaoEncontrada,
    CorrectionService,
    JustificativaObrigatoria,
)
from gestlog.db.models import ItemCorrecao, Membership, User
from gestlog.repositories.catalog import (
    StockRepository,
    SupplierRepository,
    TransportRepository,
)
from gestlog.web.ingestion_ui import get_sync_session
from gestlog.web.schemas import DecisaoCorrecao

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_DECISOES = get_args(DecisaoCorrecao)
_LIMITE_PADRAO = 200
_LIMITE_MAXIMO = 500
_CATALOGOS = (StockRepository, SupplierRepository, TransportRepository)


def _tem_dados(session: Session, empresa_id: UUID) -> bool:
    """Indica se a empresa tem ao menos um registro nos catálogos."""
    return any(fabrica(session).list(empresa_id) for fabrica in _CATALOGOS)


def _agrupar(itens: list[ItemCorrecao]) -> dict[str, list[ItemCorrecao]]:
    """Agrupa os itens por tipo, preservando a ordem de criação."""
    grupos: dict[str, list[ItemCorrecao]] = {}
    for item in itens:
        grupos.setdefault(item.tipo, []).append(item)
    return grupos


def _render(
    request: Request,
    session: Session,
    vinculo: Membership,
    usuario: User,
    limite: int,
    erro: str | None = None,
    status_code: int = status.HTTP_200_OK,
) -> HTMLResponse:
    """Materializa a fila e renderiza a página, opcionalmente com erro."""
    servico = CorrectionService(session, vinculo.empresa_id)
    servico.gerar_fila()
    pendentes = servico.listar("pendente", limite)
    return _TEMPLATES.TemplateResponse(
        request,
        "correcoes.html",
        {
            "titulo": "Correções · gestlog",
            "grupos": _agrupar(pendentes),
            "quantidade": len(pendentes),
            "limite": limite,
            "tem_dados": _tem_dados(session, vinculo.empresa_id),
            "erro": erro,
            "email": usuario.email,
            "admin": vinculo.papel == "admin",
            "pode_aprovar": vinculo.papel in PAPEIS_APROVADORES,
        },
        status_code=status_code,
    )


def create_correcoes_router() -> APIRouter:
    """Cria as rotas da fila de correções e da decisão de aprovar/rejeitar."""
    router = APIRouter()

    @router.get("/correcoes", response_class=HTMLResponse)
    def pagina_correcoes(
        request: Request,
        usuario: Annotated[User, Depends(get_current_user)],
        vinculo: Annotated[Membership, Depends(exigir_papel(*PAPEIS_APROVADORES))],
        session: Annotated[Session, Depends(get_sync_session)],
        limite: Annotated[int, Query(ge=1, le=_LIMITE_MAXIMO)] = _LIMITE_PADRAO,
    ) -> Response:
        """Gera e lista os itens pendentes da empresa, agrupados por tipo."""
        return _render(request, session, vinculo, usuario, limite)

    @router.post("/correcoes/{item_id}/decisao", response_class=HTMLResponse)
    def decidir_correcao(
        item_id: UUID,
        request: Request,
        usuario: Annotated[User, Depends(get_current_user)],
        vinculo: Annotated[Membership, Depends(exigir_papel(*PAPEIS_APROVADORES))],
        session: Annotated[Session, Depends(get_sync_session)],
        decisao: Annotated[str, Form()] = "",
        justificativa: Annotated[str, Form()] = "",
        limite: Annotated[int, Query(ge=1, le=_LIMITE_MAXIMO)] = _LIMITE_PADRAO,
    ) -> Response:
        """Aprova ou rejeita um item e redireciona (PRG), reexibindo em erro."""
        if decisao not in _DECISOES:
            return _render(
                request,
                session,
                vinculo,
                usuario,
                limite,
                erro="Decisão inválida.",
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        servico = CorrectionService(session, vinculo.empresa_id)
        try:
            if decisao == "aprovar":
                servico.aprovar(item_id, usuario.id, vinculo.papel)
            else:
                servico.rejeitar(item_id, usuario.id, vinculo.papel, justificativa)
        except CorrecaoNaoEncontrada:
            return _render(
                request,
                session,
                vinculo,
                usuario,
                limite,
                erro="Item de correção não encontrado.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        except JustificativaObrigatoria as exc:
            return _render(
                request,
                session,
                vinculo,
                usuario,
                limite,
                erro=str(exc),
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
        except (CorrecaoNaoAprovavel, CorrecaoAlvoInvalido) as exc:
            return _render(
                request,
                session,
                vinculo,
                usuario,
                limite,
                erro=str(exc),
                status_code=status.HTTP_409_CONFLICT,
            )
        return RedirectResponse(url="/correcoes", status_code=status.HTTP_303_SEE_OTHER)

    return router
