# Contexto da Sessão — Postgres no CI (matriz de dialetos)
> Handoff persistente. `/end` grava, `/start` lê. Última atualização: 2026-10-22.
> Branch: `main` · HEAD: `912a429` (= `origin/main`)

## Estado atual
- **gestlog**: fluxo multiagente LangGraph (supervisor + transporte/fornecedores/estoque)
  com tools `@tool`. Remote `origin` = https://github.com/Andreson1010/gestlog (privado).
- `main` @ `912a429` (= `origin/main`) · tags `v0.1.0`, `v0.2.0`, `v0.3.0` (F2) e
  `v0.4.0` (relatórios operacionais). `pyproject`/`uv.lock` em **0.4.0**.
- **AD-027 QUITADO** — ✅ concluído (PR #73, squash `912a429`, branch apagada): as 5 FKs de
  `user.id` (`membership.user_id`, `conversation.user_id`, `feedback.user_id`,
  `audit_log.user_id`, `item_correcao.decidido_por`) passaram de `Uuid` (hex 32, sem hífen)
  para `GUID` do FastAPI Users (36, com hífen no SQLite; `UUID` nativo no Postgres);
  `auth/accounts.py::listar_usuarios` trocou o workaround `User.id.in_(ids)` por JOIN direto;
  migração `b7d2e9a4f108` normaliza valores legados 32→36 no SQLite (no-op em UUID nativo).
  Decisão em **AD-030** (`docs/specs/project/STATE.md`); ADR
  `docs/adr/ad027-alinha-fk-user-guid-self-review.md`.
- **Follow-ups de relatórios FU-1..FU-7** — ✅ todos resolvidos (PRs #68..#72); nenhum aberto.
- **Feature relatórios operacionais** — ✅ mergeada (PR #66); **release v0.4.0** (PR #67, tag anotada).
- Stack (AD-007): FastAPI + Jinja2/HTMX/SSE + Postgres (`empresa_id`) + FastAPI Users.
- **Harness de dev**: `http://127.0.0.1:8000` (login `demo@gestlog.local` / `demo12345`),
  `serve_dev.py` fora do repo.

## O que foi feito nesta sessão (2026-10-22)
- **Validação do handoff**: `main` @ `912a429` = `origin/main`, tags até `v0.4.0`,
  versão `0.4.0`, AD-027 ✅, FU-1..FU-7 ✅ — sem divergências (nada a corrigir).
- **Frente escolhida pelo usuário**: quitar o débito herdado **Postgres no CI
  (matriz de dialetos)** — follow-up explícito da ADR AD-027.
- **Branch**: `refactor/postgres-no-ci` (cortada de `main`).
- **Implementação**:
  - `tests/conftest.py`: `url_postgres`/`engine_postgres` (session) + `db_session`
    dialeto-aware (Postgres com transação externa + savepoints via
    `join_transaction_mode="create_savepoint"`, teardown com rollback).
  - `tests/test_migrations.py`: `alembic_config` cria banco Postgres descartável por
    teste (CREATE/DROP DATABASE via conexão admin autocommit em `postgres`); teste
    SQLite de dados legados ganhou guard de dialeto; novo
    `test_migracao_postgres_nao_altera_fk_user` (no-op com UUID nativo); `"user"`
    entre aspas no SQL cru (palavra reservada no PG); `TRUE/FALSE`; `_como_utc`.
  - `tests/apoio.py` (novo): `criar_usuario`/`criar_empresa` — pais reais para FKs
    (com `commit`, pois o `rollback` interno do `CorrectionService` desfaria a
    inserção pendente no modo savepoint).
  - Fixes de FKs órfãs (53 testes que passavam só porque o SQLite não aplica FK):
    `tests/{audit,copilot,correcoes}/*`, `tests/test_repositories*.py`.
  - `.github/workflows/ci.yml`: job `postgres` (service `postgres:16`, env
    `GESTLOG_TEST_DATABASE_URL`, `uv run pytest --no-cov`).
  - Docs: `docs/specs/project/STATE.md` (**AD-031** + AD-030 aponta p/ ela),
    `docs/specs/codebase/TESTING.md` (comando matrix), `README.md`.
- **Validação local**: gate SQLite (WSL2) **572 passed, 1 skipped, 99.23%**;
  suíte completa no Postgres local (Docker `gestlog-pg`, porta 5433)
  **572 passed, 1 skipped**. Script de apoio:
  `C:\Users\ander\AppData\Local\Temp\opencode\gestlog-pg-gate.sh`.
- **Self-review** (`developer-self-reviewer`): achado médio corrigido —
  `tests/test_db.py` tinha fixture própria em SQLite (camada de modelos fora da
  matriz); 3 testes de dados migrados para `db_session` (6 passed nos dois
  dialetos). STATE ajustado (~120 testes com `db_session`, medido). ADR
  `docs/adr/postgres-ci-self-review.md`; lição **L-038**. Gates reexecutados
  verdes pelo self-review e revalidados por mim.
- **Pendente**: code review (`code-reviewer-agent`), PR, CI verde, merge.

## Decisões e regras (não esquecer)
- **FK para `user.id` usa `GUID`** (não `Uuid`): é o tipo do `User.id` do FastAPI Users; no
  SQLite `Uuid` grava hex 32 e `GUID` grava 36 com hífen — misturar quebra JOIN.
- **Recorte de período**: fonte única `web/periodo.py` (`inicio_do_dia`/`fim_do_dia`).
- **Relatórios**: empresa de `exigir_papel(*PAPEIS_APROVADORES)` (nunca URL/query); 401 sem
  sessão, 403 operador, 404 domínio inválido, 422 `de > ate`/data malformada; recorte UTC
  inclusivo; CSV `;`/`utf-8-sig`/RFC 4180 com o mesmo formatador da tela.
- **Processo**: self-review (`developer-self-reviewer` + ADR) e code review independente
  (`code-reviewer-agent`, `opencode-go/glm-5.3-flash`, só reporta). Squash-merge por PR;
  `main` **nunca** recebe push direto.
- **Supervisor anti-loop**: repetir especialista → `FINISH`. Memória de erros em `.opencode/LESSONS.md`.

## Próximos passos / bloqueios
1. **Débitos herdados** (próximos candidatos; nenhum em andamento):
   - `String(4000)`/`Text` (migração pontual em `message.conteudo_redigido`/`recommendation.texto`);
   - **Postgres no CI** (matriz de dialetos) — follow-up explícito da ADR AD-027; cobriria o
     ramo no-op da migração;
   - T23/AD-019: botões no turno ao vivo (SSE) + ordenação monotônica de mensagens;
   - rate limiting e convite por token (AD-015); seleção de "empresa ativa"; `evals/` no CI.
2. **Gate local via WSL2** (contorna o Smart App Control): `wsl -d Ubuntu -u root -- gestlog-gate`
   → **572 passed, 99.23%**. Focado: `... gestlog-gate tests/test_migrations.py --no-cov -q`;
   lint só: `... gestlog-gate lint`. Venv Linux fora do repo (`UV_PROJECT_ENVIRONMENT=/root/.venvs/gestlog`).
3. **Sem bloqueios ativos.**

## WIP local (não commitado)
- `.opencode/CONTEXT.md` (este arquivo) e `.opencode/LESSONS.md` — handoff/lessons, não
  versionados (regra: `main` não recebe push direto).
- `docs/business/KipperDev-Guia-Seguranca-Vibe-Coding.pdf` — não rastreado (não é desta sessão).

## Artefatos do graphify
- **graphify indisponível** (verificado nesta sessão: sem tool `graphify_*`; `list_mcp_resources`
  → `[]` e `list_mcp_resource_templates` → `[]`). Números **não verificados** — não inventar.

## Documentos de projeto relevantes
- **Feature relatórios**: `docs/specs/features/relatorios-operacionais/{story,spec,design,tasks}.md`.
- **Features anteriores**: `docs/specs/features/{f1-mvp,f2-hitl,ui-beautifului}/*`.
- **Projeto**: `docs/specs/project/{PROJECT,ROADMAP,STATE}.md`; `docs/specs/codebase/TESTING.md`;
  `docs/business/` (PRD + PDF não rastreado).
- **Mudou nesta sessão**: `docs/specs/project/STATE.md` (**AD-030** + débitos);
  `docs/adr/ad027-alinha-fk-user-guid-self-review.md` (novo); `.opencode/LESSONS.md` (L-037);
  `.opencode/CONTEXT.md`.
- **Código/testes desta sessão**: `src/gestlog/db/models.py`, `src/gestlog/auth/accounts.py`,
  `alembic/versions/b7d2e9a4f108_alinhar_fk_user_guid.py`, `tests/test_migrations.py`.
- **Config/skills**: `AGENTS.md`, `README.md`, `Makefile`, `opencode.json`;
  `.opencode/skills/*`; `.opencode/agent/*`. Plugin `self-learning.ts`.
- **PR/branch**: PR #73 (`refactor/ad027-alinha-fk-user-guid`, `912a429`) **MERGED**; apagada.

---
# Histórico (sessões anteriores, resumido)
- **2026-10-07 (esta sessão)**: validação do handoff (sem divergências) + quitação do débito
  **AD-027** (FKs de `user.id` → `GUID`, JOIN direto, migração `b7d2e9a4f108`); self-review +
  ADR + code review APPROVE; **PR #73** (`912a429`).
- **2026-10-06**: validação do handoff + code review/merge de FU-2 (#70), FU-3/FU-4/FU-6 (#71)
  e FU-7 (#72); setup do gate local via WSL2. FU-1..FU-7 encerrados.
- **2026-10-02**: FU-5 (#69) e FU-2 implementado (PR #70); FU-6 registrado.
- **2026-09-30**: code review + merge da feature relatórios (#66), release **v0.4.0** (#67), FU-1 (#68).
- **2026-09-28**: feature relatórios operacionais (T1–T11 + self-review + aceitação); PR #66.
- **2026-09-27**: F2 T12 (#60) + release **v0.3.0** (#61); épico F2 fechado.
- **2026-09-22**: UI beautifului + release `v0.2.0`; F2 planejada; T1/T2.
- **2026-09-18**: F1 completa (34/34); release `v0.1.0`.
