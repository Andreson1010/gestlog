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
    _aplicar_registros(session, empresa_id, resultado)
    _registrar_erros(jobs, job, resultado)
    return jobs.finish(job, aceitas=resultado.aceitas)


def historico(session: Session, empresa_id: UUID) -> list[ImportJob]:
    """Lista as importações do empresa, mais recentes primeiro."""
    return ImportJobRepository(session).history(empresa_id)


def _aplicar_registros(
    session: Session, empresa_id: UUID, resultado: ResultadoImportacao
) -> None:
    estoque = StockRepository(session)
    fornecedores = SupplierRepository(session)
    transporte = TransportRepository(session)
    for registro in resultado.registros:
        if isinstance(registro, RegistroEstoque):
            _aplicar_estoque(estoque, empresa_id, registro)
        elif isinstance(registro, RegistroFornecedor):
            _aplicar_fornecedor(fornecedores, empresa_id, registro)
        elif isinstance(registro, RegistroTransporte):
            _aplicar_transporte(transporte, empresa_id, registro)


def _aplicar_estoque(
    repo: StockRepository, empresa_id: UUID, registro: RegistroEstoque
) -> None:
    repo.upsert(
        empresa_id,
        registro.sku,
        registro.nome,
        registro.quantidade,
        registro.minimo,
        registro.local,
    )


def _aplicar_fornecedor(
    repo: SupplierRepository, empresa_id: UUID, registro: RegistroFornecedor
) -> None:
    repo.upsert(
        empresa_id,
        registro.fornecedor_id,
        registro.nome,
        registro.categoria,
        registro.prazo_dias,
        registro.avaliacao,
        registro.ativo,
    )


def _aplicar_transporte(
    repo: TransportRepository, empresa_id: UUID, registro: RegistroTransporte
) -> None:
    repo.upsert(
        empresa_id,
        registro.codigo_rastreio,
        registro.origem,
        registro.destino,
        registro.peso_kg,
        registro.status,
    )


def _registrar_erros(
    jobs: ImportJobRepository, job: ImportJob, resultado: ResultadoImportacao
) -> None:
    for erro in resultado.erros:
        jobs.add_error(job, erro.linha, erro.motivo)
