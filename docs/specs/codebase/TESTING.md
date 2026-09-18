# Testing — gestlog (brownfield)

**Stack:** Python >= 3.11, pytest (+ pytest-asyncio, pytest-cov), black, ruff.
**Framework de testes:** `tests/` espelha `src/`; modelos LLM sempre fakes.

## Commands

| Gate | Command |
| --- | --- |
| quick | `uv run pytest tests/<caminho> --no-cov -q` |
| full | `uv run pytest` (gate de cobertura 80% via `addopts`) |
| lint | `uv run ruff check src/ tests/` |
| format | `uv run black --check src/ tests/` |

## Test Coverage Matrix

| Code layer | Required test type | Parallel-safe |
| --- | --- | --- |
| `config` / settings | unit | Yes |
| `privacy` (PII redaction) | unit | Yes |
| `ingestion` parsers/validators | unit | Yes |
| `tools` (tenant-scoped) | unit | Yes |
| `copilot` service / metering | unit (fake model) | Yes |
| `evaluation` golden set | unit (fake model) | Yes |
| DB models / repositories | integration (SQLite em memória por teste; Postgres no CI) | No |
| `auth` / tenancy guards | integration | No |
| `web` rotas (HTMX/SSE) | integration (`httpx`/TestClient) | No |
| Fluxos de aceitação (P1) | e2e | No |

**Rules:** testes co-localizados na task que cria a camada; nenhum teste toca rede
(LLM/DB externo). `Tests: none` só quando a camada for infra (ex.: dependências).

## Parallelism Assessment

- **Parallel-safe (Yes):** camadas puramente unit (config, privacy, parsers,
  tools com fake repo, copilot/eval com fake model).
- **Not parallel-safe (No):** qualquer camada que use DB compartilhado ou
  TestClient com app/DB comum — rodar sequencialmente por fase.
