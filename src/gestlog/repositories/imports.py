"""Repositório de importações."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from gestlog.db.models import ImportJob, ImportJobError
from gestlog.repositories.base import EmpresaScopedRepository


class ImportJobRepository(EmpresaScopedRepository[ImportJob]):
    """Importações e seus erros, sempre por empresa."""

    model = ImportJob

    def create_job(
        self, empresa_id: UUID, tipo: str, status: str = "processando"
    ) -> ImportJob:
        """Cria uma execução de importação."""
        return self.add(ImportJob(empresa_id=empresa_id, tipo=tipo, status=status))

    def add_error(self, job: ImportJob, linha: int, motivo: str) -> ImportJobError:
        """Registra um erro de linha e incrementa o contador de rejeitadas."""
        erro = ImportJobError(import_job_id=job.id, linha=linha, motivo=motivo)
        self.session.add(erro)
        job.rejeitadas += 1
        self.session.flush()
        return erro

    def finish(
        self, job: ImportJob, aceitas: int, status: str = "concluido"
    ) -> ImportJob:
        """Finaliza a importação com o total de linhas aceitas."""
        job.aceitas = aceitas
        job.status = status
        self.session.flush()
        return job

    def history(self, empresa_id: UUID) -> list[ImportJob]:
        """Lista as importações do empresa, mais recentes primeiro."""
        stmt = (
            select(ImportJob)
            .where(ImportJob.empresa_id == empresa_id)
            .order_by(ImportJob.created_at.desc())
        )
        return list(self.session.execute(stmt).scalars().all())
