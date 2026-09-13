# Contexto da Sessão — F1 do gestlog: processo maduro + T10/T11

> Handoff persistente. `/end` grava, `/start` lê. Última atualização: 2026-09-13.
> Branch: `feat/f1-mvp` (integração) · HEAD: `c5ee5e7` · Entrega: épico + 1 PR por task (AD-016)

## Estado atual

- **gestlog**: fluxo multiagente em LangGraph (supervisor + especialistas
  transporte / fornecedores / estoque) com tools `@tool` de dados mockados.
  Remote `origin` = https://github.com/Andreson1010/gestlog (privado).
- **F1 (MVP) em execução** na branch de integração `feat/f1-mvp`: **T1–T11
  concluídos**; **23 tasks restantes (T12–T34)**. Stack travado (AD-007):
  FastAPI + Jinja2/HTMX/SSE + Postgres (`empresa_id`) + FastAPI Users.
- **Modelo de entrega (AD-016)**: `main` verde com CI; `feat/f1-mvp` é a branch de
  integração; **1 PR por task** (`feat/f1-tXX-*` → `feat/f1-mvp`) com CI +
  `code-reviewer`; release único `feat/f1-mvp → main` + tag `v0.1.0`. Os PRs
  stacked #1/#2/#3 foram fechados. Ver `AGENTS.md` §"Fluxo da feature (épico + task)".
- **CI**: `.github/workflows/ci.yml` na `main` (`f639f36`) — `black --check`,
  `ruff check`, `pytest` (gate 80%) em PRs e push para `main`/`feat/f1-mvp`.
- **Suíte**: **81 testes, 96,76% de cobertura** (`uv run pytest`); Python 3.14.3
  no `.venv` (projeto exige `>=3.11`).
- **Estrutura**: `src/gestlog/` (`config`, `llm`, `state`, `graph`, `cli`,
  `agents/`, `tools/`, `db/`, `repositories/`, `auth/`, `web/`, `ingestion/`),
  `alembic/`, `tests/` espelhando `src/`. Produto em `docs/business/PRD.md` +
  `docs/specs/`.

## O que foi feito nesta sessão (2026-09-13)

- **Validação do handoff anterior** contra o repo (suíte/branches/commits) e
  correção do `CONTEXT.md` (WIP, contagem de commits, seção graphify).
- **Code review dos 3 PRs stacked** (skill `code-reviewer`) e correções:
  CRITICAL (segredo de JWT público → AD-014), MEDIUM (tenancy determinística;
  onboarding/convite atômicos) e LOW (Literals mortos, `ImportError`→`ImportJobError`,
  SRI do htmx). Hardening adiado (AD-015).
- **Stacked reescrito** para propagar os fixes às branches de fase (commits scoped
  por fase, `--force-with-lease`; conteúdo final idêntico ao anterior).
- **Adoção do fluxo maduro** (pedido do usuário): **CI** (PR #4) + **épico + 1 PR
  por task** (PR #5, **AD-016**). Stacked #1/#2/#3 fechados.
- **T10 concluído** (PR #6, `5c10370`): `GET /` exige sessão (303 → `/login`);
  `GET /login` renderiza formulário (HTMX → `POST /auth/login`); nova dep
  `current_active_user_optional`.
- **T11 concluído** (PR #8, `debdddd`): pacote `src/gestlog/ingestion/` — leitura
  CSV (`,`/`;`) e XLSX, validação/normalização por tipo (estoque/fornecedores/
  transporte) com erros por linha.
- Handoffs intermediários: PRs #7, #9 e #10 (só `CONTEXT.md`).

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
- **AD-016**: fluxo épico + 1 PR por task, gate CI + code review, **proibido
  force-push** em `main`/`feat/f1-mvp`; release único no fim da F1.

## Próximos passos / bloqueios

1. **T12** — serviço de importação e status (persistir `ImportJob`/`ImportError`,
   upsert e histórico por empresa). Branch curta `feat/f1-t12-import-service` →
   PR contra `feat/f1-mvp`. Depende de T5 + T11. Depois **T13** (UI de upload).
   - Política de upsert (open question no `design.md`): os repositórios do T5 já
     implementam **substituir** (`upsert`); seguir com esse comportamento salvo
     indicação contrária.
2. Ao fechar a F1: PR de release `feat/f1-mvp → main` + tag `v0.1.0`.
3. Adiados (AD-015): rate limiting em auth/onboarding/convites; convite por token;
   seleção de "empresa ativa" para usuários com múltiplos vínculos.
4. Opcional: avaliar o plugin `@opencode-ai/plugin` (rodar `npm install` em
   `.opencode/`; o `node_modules/` não foi copiado).

## WIP local (não commitado)

- **Árvore limpa** (fora este `CONTEXT.md`, a commitar via chore PR).
- `main` = `f639f36`; `feat/f1-mvp` (integração) = `c5ee5e7`; **nenhum PR aberto**.
- Nenhuma task em andamento; **T12** é a próxima.
- **Backups locais** `backup/f1-fase1|f1-fase2|f1-mvp` existem (pré-rewrite do
  stacked); sem uso — podem ser removidos com `git branch -D`.
- Worktrees: nenhum (só o principal).

## Artefatos do graphify

- **graphify indisponível para este projeto**: não existe `graphify-out/graph.json`
  no gestlog (verificado; `Test-Path` = falso).
- O MCP `graphify` do `opencode.json` aponta para o grafo do **medasist**
  (`C:\Users\ander\8_projetos\medasist\graphify-out\graph.json`); os números que ele
  retorna são de outro repositório e **não** representam o gestlog.

## Documentos de projeto relevantes

- `AGENTS.md` — arquitetura, convenções, comandos e fluxo épico+task (fonte de verdade).
- `docs/business/PRD.md` — PRD do produto.
- `docs/specs/project/{PROJECT,ROADMAP,STATE}.md` — TLC; decisões AD-001..AD-016.
- `docs/specs/features/f1-mvp/{spec,design,tasks}.md` — planejamento da F1.
- `docs/specs/codebase/TESTING.md` — matriz de testes e gates.
- `README.md`, `pyproject.toml`, `.github/workflows/ci.yml`.
- `src/gestlog/config.py` — `Settings`/`get_settings()`; `tests/conftest.py` —
  `FakeChatModel`/`fake_model_cls`.
- `.opencode/skills/` — build-with-tests, code-reviewer, feature-factory,
  git-workflow, ship-feature.
- `.opencode/agent/` — codebase-researcher, story-writer, spec-writer,
  backend-builder, frontend-builder, test-verifier, validator, persistence-checker.

---
# Histórico (sessões anteriores, resumido)

- **2026-09-13:** validação do handoff; code review dos 3 PRs stacked + correções
  (AD-014/015); stacked reescrito para propagar fixes; adoção do fluxo épico +
  1 PR por task com CI (AD-016); T10 (PR #6) e T11 (PR #8) concluídos.
- **2026-09-12:** inventário de tools formalizado (AD-010); docs-as-code
  `.specs/`→`docs/specs/` (AD-011, `4da4153`); fronteiras do pacote (AD-012);
  camada async do auth (AD-013); T6 login/logout (`68bc21e`), T7 tenancy
  (`4dfdbdc`), T8 onboarding/convites (`c42f710`), T9 app factory (`943f0cb`);
  PRs stacked #1/#2/#3.
- **2026-09-11:** scaffold `.opencode/` copiado e generalizado; PRD + artefatos
  TLC; git inicializado (`main`, `31c7368`), remote publicado; F1 planejada e Fase 1
  concluída (`8438baa`); rename `Tenant`→`Empresa`.
