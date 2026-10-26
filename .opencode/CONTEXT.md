# Contexto da Sessão — revisão de modelos + follow-ups do PR #74

> Handoff persistente. `/end` grava, `/start` lê. Última atualização: 2026-10-26.
> Branch: `main` · HEAD `7d7999f` + PR #76 (branch `chore/wip-pos-74`, head `895fafc`;
> no squash-merge do #76 este arquivo entra já na versão atualizada).

## Estado atual

- **gestlog**: fluxo multiagente LangGraph (supervisor + transporte/fornecedores/estoque)
  com tools `@tool`. Remote `origin` = https://github.com/Andreson1010/gestlog (privado).
- `main` @ `7d7999f`; tags `v0.1.0`..`v0.4.0`; `pyproject`/`uv.lock` em **0.4.0**.
- **PR #74 MERGED** (squash `24128ac`): a suíte roda em Postgres no CI (matriz de dialetos;
  AD-031 no STATE). **PR #75 MERGED** (squash `7d7999f`): follow-ups do review do #74.
  Branches apagadas (local e remota). **PR #76**: WIP de config/docs comitado
  (3 commits) — merge pendente no momento da gravação deste handoff.
- **Modelos (tudo pago)**: default do projeto e builders em `opencode-go/glm-5.3-flash`;
  revisor `code-reviewer-agent` em `opencode-go/deepseek-v4.1-flash` (independência real
  de lab). Ambos testados OK após a renovação da key do `opencode-go`.
- Stack (AD-007): FastAPI + Jinja2/HTMX/SSE + Postgres (`empresa_id`) + FastAPI Users;
  LLM via endpoint compatível com OpenAI (Ollama local por padrão).
- **Harness de dev**: `http://127.0.0.1:8000` (login `demo@gestlog.local` / `demo12345`),
  `serve_dev.py` fora do repo.

## O que foi feito nesta sessão

- **Code review desbloqueado**: causa dos 3 travamentos do `code-reviewer-agent` era
  `bash "*": ask` (em subagente não-interativo o pedido de aprovação bloqueia a tool call).
  Trocado por allowlist read-only + catch-all `deny` em
  `.opencode/agent/code-reviewer-agent.md`; lição **L-040**.
- **Modelos verificados**: `opencode/*-free` existem e respondem, mas o GLM free é
  200K/32K e lento (7–196 s); o DeepSeek free foi rápido. Usuário decidiu **tudo pago**;
  config ajustada/validada (após ida-e-volta registrada em **L-039**).
- **PR #74**: code review independente → **APPROVE** (0 CRITICAL/HIGH, 1 MEDIUM + 3 LOW);
  squash-merge `24128ac`; branch `refactor/postgres-no-ci` apagada. O LOW-4 era **válido**
  (`.opencode/CONTEXT.md`/`LESSONS.md` estavam no commit) — meu descarte inicial foi
  corrigido; lição **L-041**.
- **PR #75 (follow-ups)**: `PRAGMA foreign_keys=ON` no SQLite do `db_session` (+ teste
  ancorado em FK órfã), `pythonpath = ["src", "tests"]`, nota de `CONNECT`/`postgres` no
  `TESTING.md`; ADR `docs/adr/pr74-review-followups-self-review.md`; self-review + code
  review **APPROVE** (2 LOW documentais corrigidos); squash-merge `7d7999f`.
- **Gates**: SQLite **573 passed, 1 skipped, 99.23%**; Postgres **573 passed, 1 skipped**;
  CI `quality` + `postgres` verdes nos dois PRs.
- **Documento didático**: `docs/adr/pr74-review-followups-explicacao.md` criado;
  commitado no PR #76 (commit `895fafc`), com linhas do `ci.yml` corrigidas no review.

## Decisões e regras (não esquecer)

- **Modelos**: builders/default `opencode-go/glm-5.3-flash`; revisor
  `opencode-go/deepseek-v4.1-flash` (lab independente). Free tier: 200K/32K, lento,
  promo temporária — não usar sem confirmar trade-off.
- **Subagente**: nunca `bash "*": ask`; allowlist read-only explícita + `deny`
  (falha rápida) e prompt sem pipe/variável/backtick/script no pwsh.
- **FK no SQLite de teste**: pragma só no `db_session` (`tests/conftest.py:104-116`,
  chamado em `:130`), **nunca** em `build_engine` — produção é Postgres
  (`src/gestlog/config.py:34`) e `libs` não muda por requisito de teste.
- **FK para `user.id` usa `GUID`** (não `Uuid`): `Uuid` grava hex 32 no SQLite e quebra
  JOIN com o FastAPI Users.
- **Relatórios**: empresa de `exigir_papel(*PAPEIS_APROVADORES)` (nunca URL/query);
  401 sem sessão, 403 operador, 404 domínio inválido, 422 `de > ate`/data malformada;
  recorte UTC inclusivo; CSV `;`/`utf-8-sig`/RFC 4180 com o mesmo formatador da tela.
- **Processo**: self-review (`developer-self-reviewer` + ADR) → PR → code review
  independente (`code-reviewer-agent`, só reporta) → squash-merge. `main` **nunca**
  recebe push direto.
- **Supervisor anti-loop**: repetir especialista → `FINISH`. Memória de erros em
  `.opencode/LESSONS.md`.

## Próximos passos / bloqueios

1. **Débitos** (nenhum em andamento):
   - `String(4000)`/`Text` (migração pontual em `message.conteudo_redigido`/`recommendation.texto`);
   - flake de `created_at` empatado em `tests/copilot/test_service.py` (pré-existente, Windows);
   - T23/AD-019 (botões no turno ao vivo + ordenação monotônica); rate limiting/convite
     por token (AD-015); empresa ativa; `evals/` no CI.
2. **Gate local via WSL2**: `wsl -d Ubuntu -u root -- gestlog-gate` → **573 passed, 99.23%**;
   focado `... gestlog-gate tests/test_db.py --no-cov -q`; Postgres:
   `wsl -d Ubuntu -u root -- bash /mnt/c/Users/ander/AppData/Local/Temp/opencode/gestlog-pg-gate.sh`
   (Docker `gestlog-pg`, porta 5433).
3. **Sem bloqueios ativos.**

## WIP local (não commitado)

- Limpo pelo **PR #76** (branch `chore/wip-pos-74`; commits `aa8dcfc` config/revisor,
  `0b65b4a` memória de sessão, `895fafc` ADR didático — squash-merge pendente).
- Restou apenas `docs/business/KipperDev-Guia-Seguranca-Vibe-Coding.pdf` (não rastreado
  de propósito, decisão do autor).
- Follow-ups do review do #76 (LOW, para depois): sandbox/ambiente sanitizado para
  `uv run pytest` no revisor + decidir sobre `git fetch` na allowlist (L-1);
  regra da L-033 (mesmo formatador tela×CSV) removida da poda da LESSONS —
  realocar (L-3).

## Artefatos do graphify

- **graphify indisponível** — verificado agora: `opencode mcp list` → `graphify failed`
  ("MCP error -32000: Connection closed"); a config aponta para
  `C:\Users\ander\8_projetos\medasist\graphify-out\graph.json` (projeto errado).
  `list_mcp_resources` e `list_mcp_resource_templates` → `[]`. Números **não verificados**
  — não inventar.

## Documentos de projeto relevantes

- **Projeto**: `docs/specs/project/{PROJECT,ROADMAP,STATE}.md` (STATE contém AD-031).
- **Codebase**: `docs/specs/codebase/TESTING.md` (matriz Postgres + `CONNECT` + pragma).
- **Features**: `docs/specs/features/{f1-mvp,f2-hitl,ui-beautifului,relatorios-operacionais}/*`.
- **ADRs**: `docs/adr/` (43 arquivos; desta sessão:
  `pr74-review-followups-self-review.md` e `pr74-review-followups-explicacao.md`).
- **Business**: `docs/business/PRD.md`; PDF `KipperDev-Guia-Seguranca-Vibe-Coding.pdf`
  (não rastreado).
- **Config/skills**: `AGENTS.md`, `README.md`, `Makefile`, `opencode.json`,
  `.opencode/{agent,skills,plugin}/`.
- **Mudou nesta sessão**: `AGENTS.md`, `opencode.json`, 3 `.opencode/agent/*.md`,
  `.opencode/skills/ship-feature/SKILL.md`, `.opencode/LESSONS.md`,
  `docs/adr/pr74-review-followups-{self-review,explicacao}.md`,
  `docs/specs/codebase/TESTING.md`, `tests/{conftest,test_db}.py`, `pyproject.toml`.
  O #74 (mergeado agora) também trouxe `STATE.md`, `README.md` e `.github/workflows/ci.yml`.

---

# Histórico (sessões anteriores, resumido)

- **2026-10-22 (sessão anterior)**: débito Postgres no CI (matriz de dialetos) implementado;
  self-review + ADR `postgres-ci-self-review.md`; PR #74 aberto e verde; key do revisor expirada.
- **2026-10-07**: AD-027 quitado (FKs de `user.id` → `GUID`, PR #73); self-review + APPROVE.
- **2026-10-06**: code review/merge de FU-2..FU-7; gate local via WSL2 (Smart App Control).
- **2026-09-30**: feature relatórios (#66) + release v0.4.0 (#67); FU-1 (#68).
- **2026-09-18**: F1 completa (34/34) + release v0.1.0.
