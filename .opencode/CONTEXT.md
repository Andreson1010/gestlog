# Contexto da Sessão — Scaffolding opencode + PRD do gestlog

> Handoff persistente. `/end` grava, `/start` lê. Última atualização: 2026-09-11.
> Branch: main · HEAD: 31c7368

## Estado atual

- Projeto **gestlog**: fluxo multiagente em LangGraph (supervisor + especialistas
  transporte / fornecedores / estoque), com tools `@tool` de dados mockados.
- **Repositório git inicializado** (`git init -b main`, commit raiz `31c7368`).
  Sem remote configurado ainda — `feature-factory` (Fase 0) usa `origin/main` e
  precisará de um remote.
- Suíte: **17 testes passando, 99,21% de cobertura** (`uv run pytest`),
  Python 3.14.3 no `.venv` (projeto exige `>=3.11`).
- Estrutura: `src/gestlog/` (`config`, `llm`, `state`, `graph`, `cli`,
  `agents/`, `tools/`) e `tests/` espelhando `src/`. Produto documentado em
  `docs/business/PRD.md` + `.specs/project/`.

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
  `STATE.md` em `.specs/project/`. Decisões de produto (SaaS multi-cliente,
  read-only no MVP, HITL na F2, importação→API, LLM hospedado, LGPD com redação
  de PII, fases sem datas) registradas em `.specs/project/STATE.md` (AD-001..006).
- **Git inicializado** (`git init -b main`) + `.gitignore` (com `.opencode/worktrees/`
  e `.opencode/node_modules/`) + commit raiz `31c7368` (57 arquivos).

## Decisões e regras (não esquecer)

- Skills/agentes do `.opencode/` devem permanecer **agnósticos**: especificidades
  do projeto ficam no `AGENTS.md`, nunca hardcoded nas skills.
- `uv run pytest` já ativa o gate de cobertura de 80% (`addopts`); em execuções
  focadas usar `--no-cov` (ver `AGENTS.md`).
- Nenhum teste pode tocar rede/Ollama — usar a fixture `fake_model_cls`
  (`tests/conftest.py`).

## Próximos passos / bloqueios

1. **Pendente:** configurar um **remote** (`origin`) no GitHub — o `feature-factory`
   usa `origin/main`; sem remote, criar worktree a partir de `origin/main` falha.
2. Opcional: avaliar o plugin `@opencode-ai/plugin` — se for usado, rodar
   `npm install` dentro de `.opencode/` (o `node_modules/` não foi copiado).
3. Próxima etapa de produto: design da **F1** (stack web, modelo de tenancy,
   formato do golden set) — ver `.specs/project/ROADMAP.md`.

## WIP local (não commitado)

- Limpo: tudo commitado em `31c7368`. Sem alterações pendentes.

## Artefatos do graphify

- graphify indisponível neste projeto (não há servidor MCP no `opencode.json` —
  que contém apenas `instructions: ["AGENTS.md"]`).

## Documentos de projeto relevantes

- `AGENTS.md` — arquitetura do grafo, convenções e comandos (fonte de verdade).
- `docs/business/PRD.md` — PRD completo do produto (visão, personas, requisitos,
  KPIs, roadmap, riscos).
- `.specs/project/{PROJECT,ROADMAP,STATE}.md` — artefatos TLC (visão enxuta,
  fases e memória/decisões).
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
  (`31c7368`).
