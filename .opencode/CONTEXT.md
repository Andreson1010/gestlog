# Contexto da Sessão — F1 do gestlog: T13 mergeado, T14 pendente

> Handoff persistente. `/end` grava, `/start` lê. Última atualização: 2026-09-14.
> Branch: `feat/f1-mvp` (integração) · HEAD: `a276d83` · Entrega: épico + 1 PR por task (AD-016)

## Estado atual

- **gestlog**: fluxo multiagente em LangGraph (supervisor + especialistas
  transporte / fornecedores / estoque) com tools `@tool` de dados mockados.
  Remote `origin` = https://github.com/Andreson1010/gestlog (privado).
- **F1 (MVP) em execução** na branch de integração `feat/f1-mvp`: **T1–T13
  CONCLUÍDOS** (T13 mergeado); **21 tasks PENDENTES (T14–T34)** — confirmado em
  `docs/specs/features/f1-mvp/tasks.md` (34 tasks no total).
- Stack travado (AD-007): FastAPI + Jinja2/HTMX/SSE + Postgres (`empresa_id`) +
  FastAPI Users.
- **Modelo de entrega (AD-016)**: `main` verde com CI; `feat/f1-mvp` é a branch de
  integração; **1 PR por task** (`feat/f1-tXX-*` → `feat/f1-mvp`) com CI +
  self-review + `code-reviewer`; release único `feat/f1-mvp → main` + tag
  `v0.1.0`. Stacked #1/#2/#3 fechados (não usados).
- **CI**: `.github/workflows/ci.yml` (na `main`, `f639f36`) — `black --check`,
  `ruff check`, `pytest` (gate 80%) em PRs e push para `main`/`feat/f1-mvp`.
- **Suíte**: **96 testes, 96,77% de cobertura** (`uv run pytest`, após o T13);
  Python 3.14.3 no `.venv` (projeto exige `>=3.11`).
- **Estrutura**: `src/gestlog/` (`config`, `llm`, `state`, `graph`, `cli`,
  `agents/`, `tools/`, `db/`, `repositories/`, `auth/`, `web/`, `ingestion/`),
  `alembic/`, `docs/adr/` (novo), `tests/` espelhando `src/`.

## O que foi feito nesta sessão

- **Validação do handoff anterior**; correção das divergências de WIP (commit do
  pipeline feature-factory + novo agente `developer-self-reviewer`, hoje em
  `2443b92`).
- **Commit do WIP do pipeline** (`2443b92`): `feature-factory/SKILL.md` com a
  **fase 5.5 — Developer Self-Review & ADR** + novo subagente
  `developer-self-reviewer`; enviado a `origin/feat/f1-mvp`.
- **T13 CONCLUÍDO e MERGEADO** (PR #13, squash `fcd93fc`): UI HTMX de upload e
  histórico de importação em `src/gestlog/web/ingestion_ui.py` (rotas `GET/POST
  /importar` e `GET /importar/historico`, handlers `def` no threadpool do
  FastAPI + `get_sync_session`), templates `importar.html`/
  `importar_resultado.html`/`historico.html`, CSS; 8 testes de integração.
  Gate local verde (**96 testes, 96,77%**). Code review sem CRITICAL/HIGH.
- **Self-review do T13 executado** (fase 5.5 aplicada também a tasks atômicas):
  subagente `developer-self-reviewer` corrigiu a memoização do `sessionmaker`
  sync em `ingestion_ui.py` e gerou a ADR `docs/adr/t13-upload-ui-self-review.md`
  (commit `297b77f`, incluído no PR #13).
- **Fluxo da task atualizado** em `AGENTS.md` (bullet "Self-review antes do
  review" no campo Task + "Gate antes do merge") e em `CONTEXT.md`: self-review
  com ADR é **obrigatório mesmo em tasks atômicas** (commit `6d657d5`, `a276d83`).

## Decisões e regras (não esquecer)

- **Skills/agentes do `.opencode/` são agnósticos**; especificidades do projeto
  ficam no `AGENTS.md`.
- `uv run pytest` já ativa o gate de 80% (`addopts`); use `--no-cov` em execuções
  focadas. Nenhum teste toca rede/Ollama (`fake_model_cls` em `tests/conftest.py`).
- **Nomes de código em português** (AD-008): `Empresa`/`empresa_id` (o termo
  "tenant" fica nos docs).
- **Docs-as-code** (AD-011): conceitual em `docs/`, executável em `src/`; docs
  versionados. **Pacote único** com fronteiras `apps → agents → libs` (AD-012).
- **Produto**: SaaS multi-cliente, read-only no MVP, HITL na F2, importação→API,
  LLM hospedado, LGPD/PII (AD-001..006).
- **AD-014**: `AMBIENTE=prod` exige `AUTH_SECRET` próprio (>= 32 chars).
- **AD-015**: rate limiting e convite por token adiados (hardening pós-MVP).
- **AD-016**: fluxo épico + 1 PR por task, gate CI + self-review + code review,
  **proibido force-push** em `main`/`feat/f1-mvp`; release único no fim da F1.
- **Fluxo de implementação da task** (confirmado nesta sessão):
  1. cortar `feat/f1-tXX-slug` de `feat/f1-mvp` (atualizada);
  2. implementar seguindo `build-with-tests` (sem hardcode, sem mutação,
     funções <50 linhas, docstrings em PT, sem comentários fora de docstring);
  3. testes junto do código (happy/edge/falha), gate local
     (`uv run pytest` + `black` + `ruff`);
  4. commit em PT `feat(f1): ...` e **PR contra `feat/f1-mvp`**;
  5. **self-review obrigatório** — subagente `developer-self-reviewer` (fase 5.5
     do `feature-factory`) gera `docs/adr/<slug>-self-review.md` e corrige
     achados menores; **roda também em tasks atômicas** (todo PR é revisado por
     pares);
  6. **code review obrigatório** (`code-reviewer`); Critical/Important bloqueiam;
  7. squash-merge na integração e apagar a branch.

## Próximos passos / bloqueios

1. **T13 — CONCLUÍDO e MERGEADO** (squash `fcd93fc` no `feat/f1-mvp`). UI HTMX de
   upload/histórico + self-review com ADR (`docs/adr/t13-upload-ui-self-review.md`).
2. **T14 — PENDENTE** (próxima ação): tools de estoque por empresa —
   `consultar_estoque`/`calcular_reposicao`/`listar_movimentacoes` lendo do
   repositório do tenant + novas `prever_demanda`/`otimizar_armazem`/
   `otimizar_custos`. Branch `feat/f1-t14-*` → PR contra `feat/f1-mvp`. Depende de
   T5 (repos). Fluxo da task já inclui **self-review + ADR**. Policy de upsert
   (T12) = **substituir**.
3. Ao fechar a F1: PR de release `feat/f1-mvp → main` + tag `v0.1.0`.
4. Adiados (AD-015): rate limiting em auth/onboarding/convites; convite por token;
   seleção de "empresa ativa" para usuários com múltiplos vínculos.
5. Opcional: avaliar o plugin `@opencode-ai/plugin` (rodar `npm install` em
   `.opencode/`; o `node_modules/` não foi copiado).
6. Opcional: remover os backups locais `backup/f1-fase2|f1-mvp`
   (pré-rewrite do stacked, sem uso) com `git branch -D` (f1-fase1 já removido).

## WIP local (não commitado)

- **Nenhum.** Árvore limpa (`git status` sem alterações); este handoff será o
  próximo commit.
- `main` = `f639f36`; `feat/f1-mvp` (integração) = `a276d83`; **nenhum PR aberto**.
  Branches de task `feat/f1-t12-import-service` e `feat/f1-t13-upload-ui` apagadas
  (local e remoto). Backup `backup/f1-fase1` removido localmente.

## Artefatos do graphify

- **MCP `graphify` acessível, mas o gestlog NÃO tem grafo** — `graphify_graph_stats`
  retorna erro `graph.json not found: C:\Users\ander\8_projetos\gestlog\graphify-out\graph.json`;
  `Test-Path graphify-out/graph.json` = `False`. O `opencode.json:14` aponta o MCP
  para `C:\Users\ander\8_projetos\medasist\graphify-out\graph.json`, que é de OUTRO
  repositório e **NÃO representa o gestlog**. Nenhum número registrado (não inventar).
- Comunidades afetadas: **não verificado** (sem grafo do gestlog).

## Documentos de projeto relevantes

- `AGENTS.md` — arquitetura, convenções, comandos e fluxo épico+task; agora com
  self-review obrigatório no campo Task (fonte de verdade).
- `docs/business/PRD.md` — PRD do produto.
- `docs/specs/project/{PROJECT,ROADMAP,STATE}.md` — TLC; decisões AD-001..AD-016.
- `docs/specs/features/f1-mvp/{spec,design,tasks}.md` — planejamento da F1
  (`tasks.md`: 34 tasks; T1–T13 concluídos).
- `docs/specs/codebase/TESTING.md` — matriz de testes e gates.
- `docs/adr/t13-upload-ui-self-review.md` — **novo** nesta sessão (self-review do T13).
- `README.md`, `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`.
- `src/gestlog/config.py` — `Settings`/`get_settings()`; `tests/conftest.py` —
  `FakeChatModel`/`fake_model_cls`.
- `.opencode/skills/` — build-with-tests, code-reviewer, feature-factory (fase 5.5),
  git-workflow, ship-feature.
- `.opencode/agent/` — codebase-researcher, story-writer, spec-writer,
  backend-builder, frontend-builder, **developer-self-reviewer (novo)**,
  test-verifier, validator, persistence-checker.
- `.opencode/command/` — start, end, explain, run-tests.

---

# Histórico (sessões anteriores, resumido)

- **2026-09-14:** commit do WIP do pipeline (feature-factory + `developer-self-reviewer`,
  `2443b92`); **T13 concluído e mergeado** (PR #13, squash `fcd93fc`) — UI HTMX de
  upload/histórico + 8 testes (96/96,77%); **self-review do T13** com ADR
  `docs/adr/t13-upload-ui-self-review.md`; fluxo da task passou a exigir self-review
  + ADR (`AGENTS.md`, commits `6d657d5`/`a276d83`).
- **2026-09-14 (anterior):** validação do handoff; correções de HEAD/suíte/WIP;
  confirmação de 34 tasks; `code-reviewer/SKILL.md` generalizado; **T12 concluído**
  (PR #12, `224f918`) — serviço de importação/status + 6 testes (88/97,00%).
- **2026-09-13:** code review dos 3 PRs stacked + correções (AD-014/015); adoção do
  fluxo épico + 1 PR por task com CI (AD-016); T10 (PR #6) e T11 (PR #8) concluídos.
- **2026-09-12:** catalogo de tools formalizado (AD-010); docs-as-code (AD-011);
  fronteiras do pacote (AD-012); camada async do auth (AD-013); T6-T9 concluídos.
- **2026-09-11:** scaffold `.opencode/`; PRD + artefatos TLC; git inicializado;
  remote publicado; F1 planejada e Fase 1 concluída; rename `Tenant`→`Empresa`.
