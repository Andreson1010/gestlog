# Contexto da Sessão — F1 do gestlog: T14 mergeado, T15 pendente

> Handoff persistente. `/end` grava, `/start` lê. Última atualização: 2026-09-15.
> Branch: `feat/f1-mvp` (integração) · HEAD: `12c046f` · Entrega: épico + 1 PR por task (AD-016)

## Estado atual

- **gestlog**: fluxo multiagente em LangGraph (supervisor + especialistas
  transporte / fornecedores / estoque) com tools `@tool` de dados mockados.
  Remote `origin` = https://github.com/Andreson1010/gestlog (privado).
- **F1 (MVP) em execução** na branch de integração `feat/f1-mvp`: **T1–T14
  CONCLUÍDOS** (T14 mergeado no PR #14); **20 tasks PENDENTES (T15–T34)** —
  `docs/specs/features/f1-mvp/tasks.md` (34 tasks no total).
- Stack travado (AD-007): FastAPI + Jinja2/HTMX/SSE + Postgres (`empresa_id`) +
  FastAPI Users.
- **Modelo de entrega (AD-016)**: `main` verde com CI; `feat/f1-mvp` é a branch de
  integração; **1 PR por task** (`feat/f1-tXX-*` → `feat/f1-mvp`) com CI +
  self-review + `code-reviewer`; release único `feat/f1-mvp → main` + tag
  `v0.1.0`. Stacked #1/#2/#3 fechados (não usados).
- **CI**: `.github/workflows/ci.yml` (na `main`, `f639f36`) — `black --check`,
  `ruff check`, `pytest` (gate 80%) em PRs e push para `main`/`feat/f1-mvp`.
- **Suíte**: **103 testes, 96,93% de cobertura** (`uv run pytest`, após o T14);
  Python 3.14.3 no `.venv` (projeto exige `>=3.11`).
- **Estrutura**: `src/gestlog/` (`config`, `llm`, `state`, `graph`, `cli`,
  `agents/`, `tools/`, `db/`, `repositories/`, `auth/`, `web/`, `ingestion/`),
  `alembic/`, `docs/adr/`, `tests/` espelhando `src/`.

## O que foi feito nesta sessão

- **Validação do handoff anterior contra o repo**: o arquivo dizia `T14 pendente`
  / HEAD `08001ec`, mas o `git log` mostra o **PR #14 mergeado** (`12c046f`,
  2026-09-15) e a suíte em **103 testes / 96,93%**. Handoff corrigido.
- **T14 CONCLUÍDO e MERGEADO** (PR #14, squash `12c046f`): tools de estoque por
  empresa em `src/gestlog/tools/inventory.py` — `consultar_estoque` /
  `calcular_reposicao` / `listar_movimentacoes` lendo do repositório do tenant
  (assinaturas mantidas) + novas tools read-only `prever_demanda` /
  `otimizar_armazem` / `otimizar_custos`. +114 linhas em `tests/test_tools.py`.
  Self-review com ADR `docs/adr/t14-inventory-tools-self-review.md` (extração do
  fator de excedente; reforço da ação da T19 na ADR). Coverage de
  `tools/inventory.py` = 100%.
- **Correção de `tasks.md`**: linha de progresso estava estagnada em `T12 ✅`
  (T13/T14 mergeados não marcados). Atualizada para `T1–T14 ✅`.

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
- **Fluxo de implementação da task**:
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

1. **T14 — CONCLUÍDO e MERGEADO** (squash `12c046f`). Branch remota
   `origin/feat/f1-t14-inventory-tools` **ainda não foi apagada** (limpeza
   pendente).
2. **T15 — PENDENTE** (próxima ação): tools de **fornecedores** por empresa —
   ler do repositório do tenant (assinaturas atuais) + nova `tratar_conformidade`
   (read-only na F1). Branch `feat/f1-t15-*` → PR contra `feat/f1-mvp`. Depende de
   T5. Fluxo já inclui **self-review + ADR**. (`tools/suppliers.py`, today 26
   linhas.)
3. T16 (tools de transporte por tenant) e T34 (tool comum
   `enviar_resposta_logistica`) também estão liberados a partir de T5; T17 depende
   de T14/T15/T16. Ordem sugerida: T15 → T16 → T34 → T17.
4. Ao fechar a F1: PR de release `feat/f1-mvp → main` + tag `v0.1.0`.
5. Adiados (AD-015): rate limiting em auth/onboarding/convites; convite por token;
   seleção de "empresa ativa" para usuários com múltiplos vínculos.
6. Opcional: avaliar o plugin `@opencode-ai/plugin` (rodar `npm install` em
   `.opencode/`; o `node_modules/` não foi copiado).
7. Opcional: remover os backups locais `backup/f1-fase2|f1-mvp`
   (pré-rewrite do stacked, sem uso) com `git branch -D` (f1-fase1 já removido).

## WIP local (não commitado)

- **`M .opencode/CONTEXT.md`** — este handoff corrigido (ainda não commitado).
- `main` = `f639f36`; `feat/f1-mvp` (integração) = `12c046f`; **nenhum PR aberto**.
  Branches de task T12/T13 apagadas (local e remoto); **`origin/feat/f1-t14-inventory-tools`
  ainda existe** (apagar). Backup `backup/f1-fase1` removido localmente.

## Artefatos do graphify

- **MCP `graphify` acessível, mas o gestlog NÃO tem grafo** — `graphify_graph_stats`
  retorna erro `graph.json not found: C:\Users\ander\8_projetos\gestlog\graphify-out\graph.json`;
  `Test-Path graphify-out/graph.json` = `False`. O `opencode.json:14` aponta o MCP
  para `C:\Users\ander\8_projetos\medasist\graphify-out\graph.json`, que é de OUTRO
  repositório e **NÃO representa o gestlog**. Nenhum número registrado (não inventar).
- Comunidades afetadas: **não verificado** (sem grafo do gestlog).

## Documentos de projeto relevantes

- `AGENTS.md` — arquitetura, convenções, comandos e fluxo épico+task; com
  self-review obrigatório no campo Task (fonte de verdade).
- `docs/business/PRD.md` — PRD do produto.
- `docs/specs/project/{PROJECT,ROADMAP,STATE}.md` — TLC; decisões AD-001..AD-016.
- `docs/specs/features/f1-mvp/{spec,design,tasks}.md` — planejamento da F1
  (`tasks.md`: 34 tasks; T1–T14 concluídos).
- `docs/specs/codebase/TESTING.md` — matriz de testes e gates.
- `docs/adr/t13-upload-ui-self-review.md`, `docs/adr/t14-inventory-tools-self-review.md`.
- `README.md`, `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`.
- `src/gestlog/config.py` — `Settings`/`get_settings()`; `tests/conftest.py` —
  `FakeChatModel`/`fake_model_cls`.
- `.opencode/skills/` — build-with-tests, code-reviewer, feature-factory (fase 5.5),
  git-workflow, ship-feature.
- `.opencode/agent/` — codebase-researcher, story-writer, spec-writer,
  backend-builder, frontend-builder, developer-self-reviewer, test-verifier,
  validator, persistence-checker.
- `.opencode/command/` — start, end, explain, run-tests.

---

# Histórico (sessões anteriores, resumido)

- **2026-09-15:** **T14 concluído e mergeado** (PR #14, squash `12c046f`) — tools
  de estoque por tenant + análises read-only; self-review com ADR
  `docs/adr/t14-inventory-tools-self-review.md`; suíte 103/96,93%; `tasks.md`
  corrigido (T13/T14 marcados).
- **2026-09-14:** commit do WIP do pipeline (feature-factory +
  `developer-self-reviewer`, `2443b92`); **T13 concluído e mergeado** (PR #13,
  squash `fcd93fc`) — UI HTMX de upload/histórico + 8 testes (96/96,77%);
  self-review do T13 com ADR `docs/adr/t13-upload-ui-self-review.md`; fluxo da
  task passou a exigir self-review + ADR (`AGENTS.md`, `6d657d5`/`a276d83`).
- **2026-09-14 (anterior):** validação do handoff; correções de HEAD/suíte/WIP;
  confirmação de 34 tasks; `code-reviewer/SKILL.md` generalizado; **T12 concluído**
  (PR #12, `224f918`) — serviço de importação/status + 6 testes (88/97,00%).
- **2026-09-13:** code review dos 3 PRs stacked + correções (AD-014/015); adoção do
  fluxo épico + 1 PR por task com CI (AD-016); T10 (PR #6) e T11 (PR #8) concluídos.
- **2026-09-12:** catálogo de tools formalizado (AD-010); docs-as-code (AD-011);
  fronteiras do pacote (AD-012); camada async do auth (AD-013); T6-T9 concluídos.
- **2026-09-11:** scaffold `.opencode/`; PRD + artefatos TLC; git inicializado;
  remote publicado; F1 planejada e Fase 1 concluída; rename `Tenant`→`Empresa`.
