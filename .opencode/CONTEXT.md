# Contexto da Sessão — F1 entregue (v0.1.0) e teste local do app

> Handoff persistente. `/end` grava, `/start` lê. Última atualização: 2026-09-18.
> Branch: `main` · HEAD: `156d749` · tag: `v0.1.0` (`1c0768c`)

## Estado atual

- **gestlog**: fluxo multiagente em LangGraph (supervisor + especialistas
  transporte / fornecedores / estoque) com tools `@tool`. Remote `origin` =
  https://github.com/Andreson1010/gestlog (privado).
- **F1 (MVP) CONCLUÍDA E RELEASADA**: 34/34 tasks; release PR #35 (`feat/f1-mvp →
  main`, squash `1c0768c`) + tag/release `v0.1.0`; `main` é a base agora.
- **Suíte**: **248 testes, 98,26% de cobertura** (`uv run pytest`); CI
  (`black --check`, `ruff check`, `pytest` gate 80%) verde em PRs e push. Python
  3.14.3 no `.venv` (projeto exige `>=3.11`).
- `main` = `156d749` (= `origin/main`, sincronia). Árvore limpa exceto
  `.playwright-mcp/` (não commitado, ver WIP). Tag local/remota `v0.1.0` presente.
- Stack travado (AD-007): FastAPI + Jinja2/HTMX/SSE + Postgres (`empresa_id`) +
  FastAPI Users; entrega por 1 PR/task com self-review (ADR) + code review (AD-016).

## O que foi feito nesta sessão

- **T24 — Redação de PII** (`src/gestlog/privacy/`): `redact` regex + allowlist, sem
  LLM. PR #25, AD-020, ADR `t24-redacao-pii-self-review.md`.
- **T25 — Integrar PII no copiloto**: pergunta redigida vai ao LLM **e** é a
  persistida (`Message.conteudo_redigido`); original não circula. PR #26, AD-021.
- **T26 — Auditoria e retenção** (`src/gestlog/audit/`): catálogo validado +
  `registrar_evento` (sem commit) e `purgar_expiradas` por empresa. PR #27, AD-022.
- **T27 — Uso/quota** (`copilot/metering.py`): `record_usage`, `check_quota` (mês,
  `QuotaExcedida`). PR #28, AD-023.
- **T28 — Integrar uso/quota**: `AgentState.tokens_usados`; bloqueio pré-chamada com
  `MENSAGEM_QUOTA_EXCEDIDA`. PR #29, AD-024.
- **T29 — Golden set** (`src/gestlog/evaluation/`, `evals/golden_set.json`). PR #30,
  AD-025.
- **T30 — Script de avaliação** (`evaluation/script.py`, `relatorio.py`,
  `evals/run_golden_set.py`). PR #31, AD-026.
- **T31 — Admin usuários/papéis** (`web/admin.py`, `auth/accounts.py`). PR #32,
  AD-027.
- **T32 — Dashboard de KPIs** (`repositories/kpis.py`, `web/kpis.py`, `kpis.html`).
  PR #33, AD-028.
- **T33 — Aceitação P1** (`tests/acceptance/test_f1_mvp.py`, 20 testes). PR #34,
  AD-029.
- **Release**: PR #35 `feat/f1-mvp → main` (squash `1c0768c`) + tag/release
  `v0.1.0`; docs finais no PR #36 (`156d749`).
- **Teste local**: subi o app web real com um harness de dev (SQLite compartilhado +
  Ollama), com conta e dados demo; validei login e páginas no navegador (Playwright).
  Detalhes em WIP/Próximos.

## Decisões e regras (não esquecer)

- **PII (T24/T25)**: determinístico, sem LLM; over-redação é o erro seguro; a versão
  redigida é a enviada e a persistida; `texto_resposta` é público no copiloto.
- **Auditoria (T26)**: `registrar_evento` sem commit (entra na unidade de trabalho);
  `detalhe` só metadados, nunca PII; SQL de purga só em `repositories/`.
- **Uso/quota (T27/T28)**: quota mensal por empresa via `Settings`; bloqueio
  best-effort pré-chamada; `QuotaExcedida` vira mensagem, sem derrubar a sessão.
- **Admin (T31)**: rotas sob `exigir_papel("admin")`; 404 entre empresas; último
  admin protegido (409); remoção apaga o vínculo (revoga acesso).
- **KPIs (T32)**: decisão vigente "última vence"; cobertura é snapshot; período em
  UTC inclusivo; guard admin/gestor.
- **Débito GUID/Uuid**: `Membership.user_id` (`Uuid`) × `User.id` (`GUID`) não fazem
  JOIN no SQLite; contornado com `IN` (AD-027). Alinhar exige migration.
- **Modelo LLM**: configurável em `src/gestlog/config.py` (`LLM_MODEL`,
  `SUPERVISOR_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_TEMPERATURE`); usados em
  `src/gestlog/llm.py`; recomendação com `SUPERVISOR_MODEL` separado em `graph.py`.
  A troca exige reiniciar o processo (`get_settings` é `lru_cache`).

## Próximos passos / bloqueios

1. **F1 entregue (v0.1.0)** — nada pendente do épico. Próximo épico: **F2** (tools de
   escrita/ação com HITL — AD-001).
2. **Teste local (opcional retomar)**: o harness de dev está/estava rodando em
   `http://127.0.0.1:8000` (login `demo@gestlog.local` / `demo12345`). O chat com o
   `qwen2.5:3b` (único baixado) tende a responder **insuficiência** por não fechar a
   recomendação com fontes. Para melhorar: baixar `qwen2.5:7b` e reiniciar apontando
   `LLM_MODEL`; ou rodar com modelo fake determinístico.
3. **Débito T23**: botões no turno ao vivo (SSE) e ordenação monotônica de mensagens.
4. **Débitos T20/T31**: `UniqueConstraint(empresa_id, user_id)`; reavaliar
   `String(4000)`/`Text`; mover `get_sync_session` para `web/deps.py`; alinhar
   `Membership.user_id` a `User.id`.
5. **Pendência pós-T17**: remover `TOOLS` mock do REPL quando a CLI ganhar banco.
6. **Auditoria faltante**: feedback e importação ainda não registram em `AuditLog`.
7. **CI**: `black`/`ruff` rodam em `src/ tests/` (o launcher `evals/` fica fora do
   workflow); alinhar em passada futura.

## WIP local (não commitado)

- `?? .playwright-mcp/` — 6 arquivos gerados pelo Playwright durante o teste do app
  (console log + snapshots YAML). Pode ser apagado; não é código.
- **Nenhuma alteração de código pendente**; `main` sincronizada com `origin/main`.
- **Harness de dev fora do repo** (não versionado):
  `C:\Users\ander\AppData\Local\Temp\opencode\gestlog_dev\serve_dev.py` (SQLite
  compartilhado async/sync, seed da conta demo, `LLM_MODEL` do ambiente com fallback
  `qwen2.5:3b`). Banco em `...\gestlog_dev\dev.db`; logs `out.log`/`err.log`; PID em
  `pid.txt`. Ollama iniciado localmente (`ollama serve`). **Pode haver um servidor
  ainda escutando em `127.0.0.1:8000`** — encerrar com `Stop-Process` no PID do
  `python` correspondente, se necessário.

## Artefatos do graphify

- **graphify indisponível para o gestlog.** `graphify_graph_stats` e
  `graphify_god_nodes` retornaram
  `graph.json not found: C:\Users\ander\8_projetos\gestlog\graphify-out\graph.json`.
  **Nenhum número registrado (não verificado); não inventar valores.**
- Não há `graphify-out/graph.json` no repo. Comunidades afetadas: **não verificado**.

## Documentos de projeto relevantes

- `AGENTS.md`, `README.md`, `Makefile`, `pyproject.toml`, `opencode.json`,
  `.env.example` (raiz).
- `docs/business/PRD.md`.
- `docs/specs/project/{PROJECT,ROADMAP,STATE}.md` — decisões AD-001..AD-029.
- `docs/specs/features/f1-mvp/{spec,design,tasks}.md` — F1 (tasks 34/34).
- `docs/specs/codebase/TESTING.md`.
- `docs/adr/t13..t33 + t34` (22 self-reviews em `docs/adr/*-self-review.md`).
- Código: `src/gestlog/{config,llm,graph,state,cli}.py`, `agents/`, `tools/`,
  `db/`, `repositories/{conversations,kpis,telemetry,...}.py`, `auth/`, `web/`,
  `copilot/{service,metering}.py`, `privacy/`, `audit/`, `evaluation/`, `ingestion/`.
- `evals/{golden_set.json,run_golden_set.py}`; `tests/acceptance/test_f1_mvp.py`.
- `.opencode/skills/`: build-with-tests, code-reviewer, feature-factory,
  git-workflow, ship-feature, write-fluid-hybrid-adr.
- `.opencode/agent/`, `.opencode/command/`.

---

# Histórico (sessões anteriores, resumido)

- **2026-09-18 (esta)**: T24–T33 concluídas e mergeadas (AD-020..AD-029); F1 completa
  (34/34); release PR #35 + tag `v0.1.0`; docs PR #36; teste local do app web
  (harness SQLite/Ollama, login demo validado no navegador).
- **2026-09-17**: T21 (PR #22, `88f5b38`), T22 (PR #23, `0dfc1dc`), T23 (PR #24,
  `5bcac81`); STATE ganhou AD-017/018/019; 139→157 testes.
- **2026-09-17 (anterior)**: T20 mergeada (PR #21, `0ab9e03` — histórico/tenancy).
- **2026-09-16**: skill `write-fluid-hybrid-adr`; T19 (PR #20, `450df94` — UI chat).
- **2026-09-15**: T14–T18/T34 (PRs mesclados); 109→125 testes.
- **2026-09-11..14**: scaffold `.opencode/`, PRD/TLC, F1 planejada, T1–T13.
