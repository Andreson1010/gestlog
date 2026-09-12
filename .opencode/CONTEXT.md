# Contexto da Sessão — Scaffolding opencode + PRD + execução da F1

> Handoff persistente. `/end` grava, `/start` lê. Última atualização: 2026-09-12.
> Branch: feat/f1-mvp · HEAD: 943f0cb · PRs stacked: #1 (Fase 1), #2 (Fase 2), #3 draft (Fase 3)

## Estado atual

- Projeto **gestlog**: fluxo multiagente em LangGraph (supervisor + especialistas
  transporte / fornecedores / estoque), com tools `@tool` de dados mockados.
- **Repositório git** com remote `origin` =
  https://github.com/Andreson1010/gestlog (privado).
- **F1 (MVP) em execução** na branch `feat/f1-mvp`: Fase 1 (T1–T5) concluída +
  rename `Tenant`→`Empresa`; **catálogo de ferramentas fechado** (AD-010);
  **T6–T8 (auth/tenancy/onboarding) e T9 (app factory + layout) concluídos**;
  T10 (home autenticada + navegação) pendente.
- **PRs incrementais abertos** (stacked): **#1** Fase 1 (`main` ← `feat/f1-fase1`),
  **#2** Fase 2 (`feat/f1-fase1` ← `feat/f1-fase2`), **#3** Fase 3 draft
  (`feat/f1-fase2` ← `feat/f1-mvp`). `main` e branches publicados no `origin`.
- Suíte: **56 testes passando, 97,47% de cobertura** (`uv run pytest`),
  Python 3.14.3 no `.venv` (projeto exige `>=3.11`).
- Estrutura: `src/gestlog/` (`config`, `llm`, `state`, `graph`, `cli`, `agents/`,
  `tools/`, `db/`, `repositories/`, `auth/`), `alembic/`, `tests/` espelhando `src/`.
  Produto documentado em `docs/business/PRD.md` + `docs/specs/`.

## O que foi feito nesta sessão

- Copiado o `.opencode/` do projeto **medasist** para o gestlog (exceto
  `node_modules/` e `worktrees/`): `agent/`, `command/`, `skills/`,
  `package.json`, `package-lock.json`, `.gitignore`, `CONTEXT.md`.
- Removida a skill `rag-pipeline-audit` (específica de RAG, não se aplica).
- **Skills generalizadas** (agnósticas de stack/projeto): `build-with-tests`,
  `code-reviewer`, `feature-factory`, `ship-feature`. `git-workflow` já era
  agnóstica — sem alteração. As skills agora leem comandos/padrões do `AGENTS.md`
  do projeto em vez de hardcodar paths do medasist.
- **Agentes generalizados**: `backend-builder`, `frontend-builder`,
  `test-verifier`, `validator`, `persistence-checker` (paths de exemplo
  `src/medasist/...` → `src/<package>/...`). `codebase-researcher`, `spec-writer`
  e `story-writer` já eram genéricos — sem alteração.
- **Commands generalizados**: `run-tests.md` (agora `uv run pytest`, com `--no-cov`
  em execuções focadas) e `explain.md` (removidas as referências ao medasist).
- Substituído este `CONTEXT.md` (antes continha o handoff do TCC/medasist).
- **PRD do produto** escrito após sessão de grilling (skill `grill-me`):
  `docs/business/PRD.md` (completo) + artefatos TLC `PROJECT.md`, `ROADMAP.md` e
  `STATE.md` em `docs/specs/project/`. Decisões de produto (SaaS multi-cliente,
  read-only no MVP, HITL na F2, importação→API, LLM hospedado, LGPD com redação
  de PII, fases sem datas) registradas em `docs/specs/project/STATE.md` (AD-001..006).
- **Git inicializado** (`git init -b main`) + `.gitignore` (com `.opencode/worktrees/`
  e `.opencode/node_modules/`) + commit raiz `31c7368` (57 arquivos). Remote
  `origin` criado (privado, GitHub `Andreson1010/gestlog`) e `main` publicado.
- **F1 planejada** (skill `tlc-spec-driven`): `docs/specs/features/f1-mvp/` com
  `spec.md`, `design.md` e `tasks.md` (33 tarefas) + `docs/specs/codebase/TESTING.md`.
  Stack travado (AD-007): FastAPI + Jinja/HTMX/SSE + Postgres (`tenant_id`) +
  FastAPI Users. Aguardando aprovação para executar.
- **F1 em execução** (branch `feat/f1-mvp`): T1 dependências, T2 `Settings`, T3
  modelos/sessão, T4 Alembic+migration, T5 repositórios por empresa, e rename
  `Tenant`→`Empresa` (AD-008). Fases 2–12 pendentes.
- **Catálogo de tools capturado e formalizado** (AD-010, 2026-09-12): inventário do
  usuário gravado no `design.md` §"Catálogo de ferramentas (F1)" — 1 tool comum
  (`enviar_resposta_logistica`) + tools por domínio. F1 só leitura/análise; escrita
  (HITL) na F2. Nomes em português (AD-008); 4 tools provisórias da AD-009
  substituídas. `tasks.md`: T14–T16 ampliadas + T34 (tool comum); T17 depende de T34.
- **Docs-as-code**: specs movidas de `.specs/` para `docs/specs/` (isolando o
  contexto conceitual do código executável em `src/`); referências atualizadas.
  **Docs são versionados** (decisão de 2026-09-12) — `docs/` entra no git.
- **Fronteiras fixadas** (AD-012): pacote único, mas com camadas conceituais
  `apps → agents → libs` documentadas no `AGENTS.md` §"Estrutura e fronteiras".
  Não virar monorepo multi-pacote enquanto não houver deploy independente.
- **T6 concluído** (2026-09-12): `src/gestlog/auth/` (`db.py`, `manager.py`,
  `backend.py`, `routes.py`) com login/logout por cookie + JWT (FastAPI Users).
  Camada **async isolada** para o auth (AD-013): `db/session.py` ganhou engine/
  session async + `aiosqlite` (dev); `config.py` ganhou `auth_cookie_name`/
  `auth_cookie_secure`. Repos/copilot seguem sync. 6 testes de integração.
- **T7 concluído** (2026-09-12): `src/gestlog/auth/deps.py` com
  `get_current_user`/`get_current_membership`/`get_current_empresa`,
  `verificar_empresa_do_recurso` (404 entre empresas) e `exigir_papel(...)` (403).
  Usa `Authenticator` (v15 removeu `FastAPIUsers.current_user`) e `get_jwt_strategy`
  resolvido por `Depends(get_settings)`. 4 testes de tenancy.
- **T8 concluído** (2026-09-12): `auth/accounts.py` (`criar_conta`/`convidar_usuario`)
  e `web/` (`__init__`, `schemas.py`, `onboarding.py`) com `POST /onboarding` (empresa
  + admin) e `POST /empresa/convites` (admin). 5 testes de integração.
- **T9 concluído** (2026-09-12): `web/app.py` (`create_app`: estáticos + auth +
  onboarding + rota base), `web/templates/base.html` (Jinja2 + htmx via CDN),
  `web/static/app.css`. 2 testes de integração (página base e asset).

## Decisões e regras (não esquecer)

- Skills/agentes do `.opencode/` devem permanecer **agnósticos**: especificidades
  do projeto ficam no `AGENTS.md`, nunca hardcoded nas skills.
- `uv run pytest` já ativa o gate de cobertura de 80% (`addopts`); em execuções
  focadas usar `--no-cov` (ver `AGENTS.md`).
- Nenhum teste pode tocar rede/Ollama — usar a fixture `fake_model_cls`
  (`tests/conftest.py`).
- Nomes de código em português (AD-008): modelo/tabela/coluna `Empresa`/`empresa_id`
  (o termo de domínio "tenant" fica nos docs).
- **Docs-as-code**: documentação conceitual em `docs/` (`business/`, `specs/`)
  separada do código executável em `src/`; docs **são versionados** (nada em
  `.gitignore`).
- **Estrutura: pacote único com fronteiras conceituais** (AD-012), não monorepo:
  `apps` (`cli.py`, `web/`, `auth/`, `copilot/`) → `agents` (`graph.py`, `state.py`,
  `agents/`, `tools/`) → `libs` (`config.py`, `llm.py`, `db/`, `repositories/`).
  Só extrair para pacotes quando houver deploy independente. Ver `AGENTS.md`
  §"Estrutura e fronteiras".

## PRs incrementais (stacked)

- **#1** `main` ← `feat/f1-fase1` (T1–T5 + docs) — pronto para review.
- **#2** `feat/f1-fase1` ← `feat/f1-fase2` (T6–T8) — stacked sobre #1; merge na ordem.
- **#3** `feat/f1-fase2` ← `feat/f1-mvp` (T9–T10) — **draft**; pronto quando o T10 fechar.
- Regra: PRs por fase, base = fase anterior; só abrir/mergear na ordem. `main` foi
  publicado (era 1 commit local à frente). Continuar a trabalhar em `feat/f1-mvp`
  (o #3 acompanha) e, a cada fase concluída, apontar a branch de fase e abrir o PR.

## Próximos passos / bloqueios

1. Continuar a F1 na **Fase 3**: **T10** (home autenticada + navegação para
   Importar/Chat; não autenticado redireciona ao login). Ver
   `docs/specs/features/f1-mvp/tasks.md`.
2. ~~Capturar as tools~~ — **resolvido em 2026-09-12** (AD-010); catálogo no
   `design.md`.
3. ~~Corrigir a descoberta de skills do projeto~~ — **resolvido**: as skills de
   `.opencode/skills/` (build-with-tests, code-reviewer, feature-factory,
   git-workflow, ship-feature) já aparecem no `skill` tool nesta sessão.
4. Opcional: avaliar o plugin `@opencode-ai/plugin` — se for usado, rodar
   `npm install` dentro de `.opencode/` (o `node_modules/` não foi copiado).

## WIP local (não commitado)

- Apenas este `.opencode/CONTEXT.md` (handoff da sessão), a commitar.
- Código limpo: **T1–T9 commitados e publicados** em `origin/feat/f1-mvp`
  (`68bc21e` T6, `4dfdbdc` T7, `c42f710` T8, `943f0cb` T9).
- `main` publicado (`dabd69a`); **11 commits** de F1 à frente de `origin/main`.
- Worktrees: nenhum (`git worktree list` = só o principal).

## Artefatos do graphify

- graphify indisponível neste projeto (não há servidor MCP no `opencode.json` —
  que contém apenas `instructions: ["AGENTS.md"]`).

## Documentos de projeto relevantes

- `AGENTS.md` — arquitetura do grafo, convenções e comandos (fonte de verdade).
- `docs/business/PRD.md` — PRD completo do produto (visão, personas, requisitos,
  KPIs, roadmap, riscos).
- `docs/specs/project/{PROJECT,ROADMAP,STATE}.md` — artefatos TLC (visão enxuta,
  fases e memória/decisões).
- `docs/specs/features/f1-mvp/{spec,design,tasks}.md` — planejamento da F1 (MVP).
- `docs/specs/codebase/TESTING.md` — matriz de testes e gates do projeto.
- `README.md` — visão geral e uso.
- `pyproject.toml` — dependências, black (88), ruff (E/W/F/I/B/UP/C4/SIM), pytest.
- `src/gestlog/config.py` — `Settings` (pydantic-settings) + `get_settings()`.
- `tests/conftest.py` — `FakeChatModel` / fixture `fake_model_cls`.
- `.opencode/skills/` — build-with-tests, code-reviewer, feature-factory,
  git-workflow, ship-feature.
- `.opencode/agent/` — codebase-researcher, story-writer, spec-writer,
  backend-builder, frontend-builder, test-verifier, validator, persistence-checker.

---
# Histórico (sessões anteriores, resumido)

- **2026-09-11 (esta sessão):** scaffolding do `.opencode/` copiado do medasist e
  generalizado (skills + agentes); PRD + artefatos TLC escritos; git inicializado
  e remoto (`31c7368`); F1 planejada e iniciada — Fase 1 concluída na branch
  `feat/f1-mvp` (`8438baa`); rename `Tenant`→`Empresa`.
- **2026-09-12 (esta sessão):** inventário de tools capturado e formalizado
  (AD-010); reorganização docs-as-code `.specs/` → `docs/specs/` versionada
  (AD-011, commit `4da4153`); fronteiras do pacote único (AD-012); T6 login/logout
  por cookie com camada async isolada (AD-013, commit `68bc21e`); T7 tenancy/guards
  (`4dfdbdc`); T8 onboarding/convites (`c42f710`); T9 app factory + layout
  (`943f0cb`); **PRs incrementais stacked #1/#2/#3** (Fase 1/2/3) e push de
  `main` + branches para o `origin`. Retomada da F1 prevista para 2026-09-13 (T10).
