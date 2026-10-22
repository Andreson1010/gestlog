# Lições (memória de erros — projeto gestlog)

> Só erro real, já corrigido e observado; mais recente no topo.
> Formato: `Gatilho / Erro / Regra / Evidência`. Ver "Loop de auto-melhoria" no `AGENTS.md`.

## L-038 · 2026-10-22 · testes/cobertura da matriz de dialetos
- **Erro**: a matriz Postgres foi ligada só ao fixture `db_session`; `tests/test_db.py` (camada de modelos) seguiu em SQLite apesar de o `TESTING.md` prometer "DB models ... Postgres no CI", e o STATE afirmava "~92 testes" quando o medido é 117 (120 com os modelos).
- **Regra**: ao criar matriz de dialetos, migre **todo** fixture de banco (inclusive os bespoke) e **meça** a cobertura alegada (STATE/ADR/TESTING) antes de fechar — estimativa não vale como número. Evidência: self-review `refactor/postgres-no-ci`; `tests/test_db.py` → `db_session` (6 passed nos dois dialetos); AD-031 corrigida.

## L-037 · 2026-10-07 · testes/conjunto + migração de dados
- **Erro**: o teste da migração de dados `b7d2e9a4f108` validava só `membership.user_id`; as outras 4 das 5 colunas do conjunto e o `downgrade` com dado ficaram sem asserção (reincidiu L-029).
- **Regra**: migração de dados que itera um conjunto de colunas exige 1 asserção por coluna (valor + efeito no JOIN), cobrindo `upgrade` **e** `downgrade` com dado legado. Evidência: `tests/test_migrations.py::test_migracao_normaliza_fk_user_para_guid`.

## L-036 · 2026-10-06 · alembic/geração + formatação
- **Erro**: briguei com o `script.py.mako` p/ deixá-lo black-clean; `${repr()}` emite aspas simples (black reformata), o `${imports}` vazio deixa linha em branco e o corpo do autogenerate nem passa pelo template.
- **Regra**: migração gerada nasce conforme via `[post_write_hooks]` (ruff --fix + black) no `alembic.ini`, que formata o arquivo inteiro; não edite o `.mako` p/ isso. Evidência: PR #72 (`f348d0b`).

## L-035 · 2026-10-06 · ambiente/Windows SAC + venv
- **Erro**: recriei o venv em 3.13 p/ driblar o Smart App Control no `_sqlite3` do 3.14; o bloqueio só migrou de DLL (`psycopg` `pq.pyd`).
- **Regra**: não troque interpretador por causa do SAC; rode o gate no **WSL2** sobre `/mnt/c` com venv fora do repo (`UV_PROJECT_ENVIRONMENT`) ou use o CI. Evidência: `gestlog-gate`/Ubuntu 26.04 → 571 passed.

## L-034 · 2026-10-06 · shell/pwsh + git/PR (absorve L-027)
- **Erro**: `head`/`tail`/`rg` não existem no pwsh; backtick em `--body` inline quebrou; `"$VAR"`/`$(...)` dentro de `wsl bash -lc "..."` são expandidos pelo pwsh.
- **Regra**: use cmdlets nativos (`Select-Object`/`Select-String`); PR/commit com markdown via `--body-file`; comando p/ WSL em script `.sh`; basename único de teste; default `""` em `Form()`; fonte canônica p/ flags/conjuntos (`PAPEIS_APROVADORES`, `get_args`); sincronize `origin` antes do PR; valide a ADR pelas 5 seções. Evidência: PRs #47/#55/#67/#68.

## L-033 · 2026-09-28 · web/formatação tela×CSV
- **Erro/Regra**: tela renderizava datetime cru e CSV `.isoformat()`; use o **mesmo** formatador e cubra comparando o texto da página com a célula do CSV. Evidência: `web/relatorios.py::_data`, `tests/web/test_relatorios.py`.

## L-032 · 2026-09-28 · tipagem (dispatchers/Select)
- **Erro/Regra**: dispatchers e `Select` sem anotação apagavam a união real; anote `_Resumo = A | B | C` e `Select[tuple[X]]` e valide antes do `getattr`. Evidência: `audit/eventos.py`; T6/T7/T9.

## L-031 · 2026-09-28 · testes/timezone SQLite
- **Erro/Regra**: datetime aware relido do SQLite volta naive; normalize (`.replace(tzinfo=UTC)`) no teste, sem alterar produção. Evidência: `tests/test_repositories.py`.

## L-030 · 2026-09-27 · testes/tamanho de arquivo
- **Erro/Regra**: não entregue arquivo > 800 linhas (nem helpers quebrados); dimensione antes e modularize (conftest/helpers/por grupo). Evidência: `tests/acceptance/f2_*` (≤487 linhas).

## L-029 · 2026-09-27 · testes/ancoragem (absorve L-026, L-028)
- **Erro/Regra**: ancore ao dado/estado do critério (não a affordance/ORM truthy); 1 teste por elemento do conjunto; autofix de linter sobre `Row` não é seguro. Evidência: `test_inc_02`; `repositories/users.py::emails` (revertido).
