"""Testes unitários da medição de uso e da quota mensal."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from gestlog.config import Settings
from gestlog.copilot.metering import (
    QuotaExcedida,
    check_quota,
    record_usage,
    uso_no_mes,
)
from gestlog.repositories.empresas import EmpresaRepository
from gestlog.repositories.telemetry import UsageRepository


def _empresa(session: Session, nome: str) -> UUID:
    empresa = EmpresaRepository(session).create(nome)
    session.commit()
    return empresa.id


def test_record_usage_soma_por_empresa(db_session: Session) -> None:
    empresa = _empresa(db_session, "A")
    outra = _empresa(db_session, "B")

    record_usage(db_session, empresa, "qwen", 100)
    record_usage(db_session, empresa, "qwen", 50)
    record_usage(db_session, outra, "qwen", 10)
    db_session.commit()

    repo = UsageRepository(db_session)
    assert repo.total_tokens(empresa) == 150
    assert repo.total_tokens(outra) == 10


def test_record_usage_rejeita_tokens_negativos(db_session: Session) -> None:
    empresa = _empresa(db_session, "A")

    with pytest.raises(ValueError):
        record_usage(db_session, empresa, "qwen", -1)


def test_uso_no_mes_soma_apenas_mes_corrente(db_session: Session) -> None:
    empresa = _empresa(db_session, "A")
    agora = datetime(2026, 6, 15, 12, tzinfo=UTC)
    repo = UsageRepository(db_session)
    antigo = repo.record(empresa, "qwen", 999)
    antigo.created_at = datetime(2026, 5, 20, 12, tzinfo=UTC)
    atual = repo.record(empresa, "qwen", 100)
    atual.created_at = agora
    db_session.commit()

    assert uso_no_mes(db_session, empresa, agora) == 100


def test_uso_no_mes_rejeita_datetime_sem_fuso(db_session: Session) -> None:
    empresa = _empresa(db_session, "A")

    with pytest.raises(ValueError):
        uso_no_mes(db_session, empresa, datetime(2026, 1, 1))


def test_check_quota_permite_abaixo(db_session: Session) -> None:
    empresa = _empresa(db_session, "A")
    record_usage(db_session, empresa, "qwen", 50)
    db_session.commit()
    settings = Settings(_env_file=None, llm_monthly_token_quota=100)

    assert check_quota(db_session, empresa, settings) == 50


def test_check_quota_bloqueia_ao_atingir(db_session: Session) -> None:
    empresa = _empresa(db_session, "A")
    record_usage(db_session, empresa, "qwen", 100)
    db_session.commit()
    settings = Settings(_env_file=None, llm_monthly_token_quota=100)

    with pytest.raises(QuotaExcedida) as excinfo:
        check_quota(db_session, empresa, settings)

    assert excinfo.value.usado == 100
    assert excinfo.value.quota == 100
    assert excinfo.value.empresa_id == empresa


def test_check_quota_isola_entre_empresas(db_session: Session) -> None:
    empresa = _empresa(db_session, "A")
    outra = _empresa(db_session, "B")
    record_usage(db_session, empresa, "qwen", 100)
    db_session.commit()
    settings = Settings(_env_file=None, llm_monthly_token_quota=100)

    assert check_quota(db_session, outra, settings) == 0
