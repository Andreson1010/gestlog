"""Aplicação de importações validadas no banco, sempre por empresa."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from gestlog.db.models import ImportJob
from gestlog.ingestion.modelos import (
    RegistroEstoque,
    RegistroFornecedor,
    RegistroTransporte,
    ResultadoImportacao,
)
from gestlog.ingestion.parser import analisar
from gestlog.repositories.catalog import (
    StockRepository,
    SupplierRepository,
    TransportRepository,
)
from gestlog.repositories.historico import HistoricoRepository
from gestlog.repositories.imports import ImportJobRepository


def importar(
    session: Session,
    empresa_id: UUID,
    tipo: str,
    conteudo: bytes,
    nome_arquivo: str = "",
) -> ImportJob:
    """Valida o arquivo, aplica upsert das linhas aceitas e grava o status.

    Arquivos inválidos (vazios, tipo desconhecido, colunas ausentes) levantam
    ``ErroImportacao`` antes de qualquer escrita, deixando os dados intactos.
    """
    resultado = analisar(tipo, conteudo, nome_arquivo)
    jobs = ImportJobRepository(session)
    job = jobs.create_job(empresa_id, tipo)
    _aplicar_registros(session, job, resultado)
    _registrar_erros(jobs, job, resultado)
    return jobs.finish(job, aceitas=resultado.aceitas)


def historico(session: Session, empresa_id: UUID) -> list[ImportJob]:
    """Lista as importações do empresa, mais recentes primeiro."""
    return ImportJobRepository(session).history(empresa_id)


def _aplicar_registros(
    session: Session, job: ImportJob, resultado: ResultadoImportacao
) -> None:
    estoque = StockRepository(session)
    fornecedores = SupplierRepository(session)
    transporte = TransportRepository(session)
    historico = HistoricoRepository(session)
    for registro in resultado.registros:
        if isinstance(registro, RegistroEstoque):
            _aplicar_estoque(estoque, historico, job, registro)
        elif isinstance(registro, RegistroFornecedor):
            _aplicar_fornecedor(fornecedores, historico, job, registro)
        elif isinstance(registro, RegistroTransporte):
            _aplicar_transporte(transporte, historico, job, registro)


def _aplicar_estoque(
    repo: StockRepository,
    historico: HistoricoRepository,
    job: ImportJob,
    registro: RegistroEstoque,
) -> None:
    repo.upsert(
        job.empresa_id,
        registro.sku,
        registro.nome,
        registro.quantidade,
        registro.minimo,
        registro.local,
        registro.categoria,
    )
    historico.registrar(
        job,
        "estoque",
        registro.sku,
        nome=registro.nome,
        categoria=registro.categoria,
        local=registro.local,
        quantidade=registro.quantidade,
        minimo=registro.minimo,
    )


def _aplicar_fornecedor(
    repo: SupplierRepository,
    historico: HistoricoRepository,
    job: ImportJob,
    registro: RegistroFornecedor,
) -> None:
    repo.upsert(
        job.empresa_id,
        registro.fornecedor_id,
        registro.nome,
        registro.categoria,
        registro.prazo_dias,
        registro.avaliacao,
        registro.ativo,
    )
    historico.registrar(
        job,
        "fornecedores",
        registro.fornecedor_id,
        nome=registro.nome,
        categoria=registro.categoria,
        prazo_dias=registro.prazo_dias,
        avaliacao=registro.avaliacao,
        ativo=registro.ativo,
    )


def _aplicar_transporte(
    repo: TransportRepository,
    historico: HistoricoRepository,
    job: ImportJob,
    registro: RegistroTransporte,
) -> None:
    repo.upsert(
        job.empresa_id,
        registro.codigo_rastreio,
        registro.origem,
        registro.destino,
        registro.peso_kg,
        registro.status,
        registro.previsao_entrega,
        registro.data_entrega,
    )
    historico.registrar(
        job,
        "transporte",
        registro.codigo_rastreio,
        origem=registro.origem,
        destino=registro.destino,
        peso_kg=registro.peso_kg,
        status=registro.status,
        previsao_entrega=registro.previsao_entrega,
        data_entrega=registro.data_entrega,
    )


def _registrar_erros(
    jobs: ImportJobRepository, job: ImportJob, resultado: ResultadoImportacao
) -> None:
    for erro in resultado.erros:
        jobs.add_error(job, erro.linha, erro.motivo)
