# Contexto da Sessão — Scaffolding opencode + PRD do gestlog

> Handoff persistente. `/end` grava, `/start` lê. Última atualização: 2026-09-11.
> Branch: — (não é repositório git) · HEAD: —

## Estado atual

- Projeto **gestlog**: fluxo multiagente em LangGraph (supervisor + especialistas
  transporte / fornecedores / estoque), com tools `@tool` de dados mockados.
- **Não é um repositório git** (`git rev-parse` falha; sem `.git/`). Isso quebra
  `/start`/`/end` (usam `git status/log/worktree`) e o `feature-factory` (Fase 0
  cria worktrees a partir de `origin/main`). Rodar `git init` quando fizer sentido.
- Suíte: **17 testes passando, 99,21% de cobertura** (`uv run pytest`),
  Python 3.14.3 no `.venv` (projeto exige `>=3.11`).
- Estrutura: `src/gestlog/` (`config`, `llm`, `state`, `graph`, `cli`,
  `agents/`, `tools/`) e `tests/` espelhando `src/`. Sem `.specs/` nem `docs/`.

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

## Decisões e regras (não esquecer)

- Skills/agentes do `.opencode/` devem permanecer **agnósticos**: especificidades
  do projeto ficam no `AGENTS.md`, nunca hardcoded nas skills.
- `uv run pytest` já ativa o gate de cobertura de 80% (`addopts`); em execuções
  focadas usar `--no-cov` (ver `AGENTS.md`).
- Nenhum teste pode tocar rede/Ollama — usar a fixture `fake_model_cls`
  (`tests/conftest.py`).

## Próximos passos / bloqueios

1. **Bloqueio:** gestlog não é repo git → `/start`, `/end` e `feature-factory`
   (worktrees/PR) não funcionam. Decidir se roda `git init` (+ remote).
2. Opcional: avaliar o plugin `@opencode-ai/plugin` — se for usado, rodar
   `npm install` dentro de `.opencode/` (o `node_modules/` não foi copiado).
3. Opcional: adicionar `.opencode/` (ou itens como `worktrees/`) ao `.gitignore`
   quando o git for inicializado.

## WIP local (não commitado)

- Sem git: **tudo** é untracked por definição. As mudanças desta sessão estão sob
  `.opencode/`, `docs/` e `.specs/` (ver "O que foi feito nesta sessão").

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
  generalizado (skills + agentes).
