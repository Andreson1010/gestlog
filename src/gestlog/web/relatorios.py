"""Relatórios operacionais por domínio, com recorte de empresa e período."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from gestlog.auth import current_active_user_optional, exigir_papel
from gestlog.correcoes import PAPEIS_APROVADORES
from gestlog.db.models import Membership, User
from gestlog.repositories.relatorios import (
    RelatorioRepository,
    ResumoEstoque,
    ResumoFornecedores,
    ResumoTransporte,
)
from gestlog.web.csv_relatorios import gerar_csv, nome_arquivo
from gestlog.web.ingestion_ui import get_sync_session
from gestlog.web.kpis import _fim, _inicio

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
_DOMINIOS = ("estoque", "transporte", "fornecedores")
_Resumo = ResumoEstoque | ResumoTransporte | ResumoFornecedores

_CABECALHOS: dict[str, tuple[str, ...]] = {
    "estoque": (
        "SKU",
        "Nome",
        "Categoria",
        "Local",
        "Quantidade",
        "Mínimo",
        "Situação",
    ),
    "transporte": (
        "Código de rastreio",
        "Origem",
        "Destino",
        "Peso (kg)",
        "Status",
        "Previsão de entrega",
        "Data de entrega",
        "Situação",
    ),
    "fornecedores": (
        "Fornecedor",
        "Nome",
        "Categoria",
        "Prazo (dias)",
        "Avaliação",
        "Status",
    ),
}


def _validar_dominio(dominio: str) -> None:
    """Responde 404 para um domínio fora dos relatórios suportados."""
    if dominio not in _DOMINIOS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Relatório não encontrado."
        )


def _validar_periodo(desde: date | None, ate: date | None) -> None:
    """Responde 422 quando a data inicial é posterior à final."""
    if desde is not None and ate is not None and desde > ate:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Período inválido: 'de' é posterior a 'até'.",
        )


def _resumo(
    session: Session,
    empresa_id: UUID,
    dominio: str,
    desde: date | None,
    ate: date | None,
) -> _Resumo:
    """Delega ao repositório do domínio, aplicando o período UTC inclusivo."""
    repo = RelatorioRepository(session)
    inicio, fim = _inicio(desde), _fim(ate)
    if dominio == "estoque":
        return repo.estoque(empresa_id, inicio, fim)
    if dominio == "transporte":
        return repo.transporte(empresa_id, inicio, fim)
    return repo.fornecedores(empresa_id, inicio, fim)


def _data(valor: datetime | None) -> str:
    """Formata uma data para o CSV, vazia quando ausente."""
    return valor.isoformat() if valor is not None else ""


def _cabecalho_linhas(
    dominio: str, resumo: _Resumo
) -> tuple[tuple[str, ...], list[tuple]]:
    """Monta o cabeçalho e as linhas da tabela principal de cada domínio."""
    if dominio == "estoque":
        linhas = [
            (
                item.chave,
                item.nome,
                item.categoria,
                item.local,
                item.quantidade,
                item.minimo,
                item.situacao,
            )
            for item in resumo.itens
        ]
    elif dominio == "transporte":
        linhas = [
            (
                registro.chave,
                registro.origem,
                registro.destino,
                registro.peso_kg,
                registro.status,
                _data(registro.previsao_entrega),
                _data(registro.data_entrega),
                registro.situacao,
            )
            for registro in resumo.registros
        ]
    else:
        linhas = [
            (
                fornecedor.chave,
                fornecedor.nome,
                fornecedor.categoria,
                fornecedor.prazo_dias,
                fornecedor.avaliacao,
                fornecedor.situacao,
            )
            for fornecedor in resumo.fornecedores
        ]
    return _CABECALHOS[dominio], linhas


def _contexto_pagina(
    dominio: str,
    resumo: _Resumo,
    usuario: User | None,
    vinculo: Membership,
    desde: date | None,
    ate: date | None,
) -> dict[str, object]:
    """Monta o contexto de template da página de relatório."""
    return {
        "titulo": "Relatórios · gestlog",
        "dominio": dominio,
        "resumo": resumo,
        "cabecalhos": _CABECALHOS[dominio],
        "desde": desde.isoformat() if desde else "",
        "ate": ate.isoformat() if ate else "",
        "email": usuario.email if usuario else "",
        "admin": vinculo.papel == "admin",
        "pode_aprovar": vinculo.papel in PAPEIS_APROVADORES,
    }


def _resposta_csv(
    dominio: str, resumo: _Resumo, desde: date | None, ate: date | None
) -> Response:
    """Monta a resposta de exportação CSV da tabela principal do domínio."""
    cabecalho, linhas = _cabecalho_linhas(dominio, resumo)
    arquivo = nome_arquivo(dominio, desde, ate)
    return Response(
        content=gerar_csv(cabecalho, linhas),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{arquivo}"'},
    )


def create_relatorios_router() -> APIRouter:
    """Cria as rotas de página e exportação por domínio operacional."""
    router = APIRouter()

    @router.get("/relatorios/{dominio}")
    def pagina_relatorio(
        request: Request,
        dominio: str,
        usuario: Annotated[User | None, Depends(current_active_user_optional)],
        vinculo: Annotated[Membership, Depends(exigir_papel(*PAPEIS_APROVADORES))],
        session: Annotated[Session, Depends(get_sync_session)],
        desde: date | None = None,
        ate: date | None = None,
    ) -> Response:
        """Renderiza a tabela e as agregações do domínio no período informado."""
        _validar_dominio(dominio)
        _validar_periodo(desde, ate)
        resumo = _resumo(session, vinculo.empresa_id, dominio, desde, ate)
        return _TEMPLATES.TemplateResponse(
            request,
            "relatorios.html",
            _contexto_pagina(dominio, resumo, usuario, vinculo, desde, ate),
        )

    @router.get("/relatorios/{dominio}/exportar")
    def exportar_relatorio(
        dominio: str,
        vinculo: Annotated[Membership, Depends(exigir_papel(*PAPEIS_APROVADORES))],
        session: Annotated[Session, Depends(get_sync_session)],
        desde: date | None = None,
        ate: date | None = None,
    ) -> Response:
        """Exporta a tabela principal do domínio em CSV, com o mesmo recorte."""
        _validar_dominio(dominio)
        _validar_periodo(desde, ate)
        resumo = _resumo(session, vinculo.empresa_id, dominio, desde, ate)
        return _resposta_csv(dominio, resumo, desde, ate)

    return router
