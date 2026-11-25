# Contexto da Sessão — skills mattpocock: instalação, poda de redundâncias e gitignore

> Handoff persistente. `/end` grava, `/start` lê. Última atualização: 2026-11-25.
> Branch: `main` · HEAD: `c45b7a2` (squash do #80) = `origin/main`.

## Estado atual

- **gestlog**: multiagente LangGraph (supervisor + transporte/fornecedores/estoque),
  FastAPI + Jinja2/HTMX/SSE + Postgres (`empresa_id`) + FastAPI Users.
- `main` @ `c45b7a2`; tags `v0.1.0`..`v0.4.0`; `pyproject`/`uv.lock` em **0.4.0**.
- **Dívidas D1–D7: TODAS MERGEADAS** (PRs #78/#79/#80, 2026-11-06) — nada de
  código em aberto.
- **Gates**: último gate (2026-11-06) → 607 passed, 1 skipped, 99,04%; nesta
  sessão NÃO houve mudança de código, gates não rodados.
- **Modelos (tudo pago)**: builders/default `opencode-go/glm-5.3-flash`; revisor
  `code-reviewer-agent` em `opencode-go/deepseek-v4.1-flash`.
- **Harness de dev**: `http://127.0.0.1:8000` (login `demo@gestlog.local` /
  `demo12345`), `serve_dev.py` fora do repo.

## O que foi feito nesta sessão (2026-11-25) — CONCLUÍDO

- **Skills mattpocock instaladas**: `npx skills@latest add mattpocock/skills
  -a opencode` → 39 skills em `.agents/skills/` (nível projeto).
- **Poda 39 → 14**:
  - 4 duplicadas removidas: `grill-me`, `grill-with-docs` (já em
    `~/.agents/skills/`), `code-review` (≈ `code-reviewer` do repo), `tdd`
    (≈ `tdd-workflow` global).
  - 21 removidas por redundância/inaplicabilidade (análise vs feature-factory,
    ship-feature, `/end`+CONTEXT.md, `/lesson`, `write-fluid-hybrid-adr`,
    allowlist opencode): `domain-modeling` (auto-invoca em ADR), `pr`
    (auto-invoca em body de PR), `setup-matt-pocock-skills`, `to-spec`,
    `to-tickets`, `wayfinder`, `triage`, `implement`, `implement-spec`,
    `software-factory` (fluxo de spec/tickets/tracker dele), `chief-of-staff`
    (memória paralela + Critical Risk Snyk), `handoff`/`claude-handoff` (vs
    `/end`), `retro` (vs `/lesson`), `research` (vs `codebase-researcher`),
    `improve-codebase-architecture`/`setup-ts-deep-modules`/
    `migrate-to-shoehorn`/`scaffold-exercises`/`setup-pre-commit` (TS/JS/Husky),
    `git-guardrails-claude-code` (hooks Claude Code; já há allowlist opencode).
  - Mantidas (14): `ask-matt`, `codebase-design`, `diagnosing-bugs`, `grilling`
    (invocada pela grill-me global), `loop-me`, `prototype`, `teach`,
    `to-questionnaire`, `wait-what`, `wizard`, `writing-beats`,
    `writing-for-agents`, `writing-fragments`, `writing-shape`.
- **`.gitignore`**: adicionadas regras para `.agents/` e `skills-lock.json`.
- **Lições**: L-051 registrada (contagem declarada vs lista real); LESSONS.md
  consolidada (29 linhas, antigos L-029..L-044 comprimidos a uma linha).
- Nenhuma mudança de código, testes ou `docs/specs/` nesta sessão.

## Decisões e regras (não esquecer)

- **Skills**: `.agents/skills/` é git-ignorado por decisão — skills de terceiros
  não versionadas no repo; antes de instalar skills novas, verificar conflito de
  gatilho (model-invoked) com skills/agentes do fluxo próprio.
- **Invocação de skills**: sem `disable-model-invocation` o agente dispara sozinho
  pela `description`; com a flag, só por comando explícito do usuário.
- **Processo**: self-review → PR → code review independente → squash-merge;
  `main` nunca recebe push direto; feature-factory (story-writer → spec-writer →
  builders → self-review → test-verifier → validator) e `ship-feature` são o
  fluxo canônico — skills externas não o contornam.
- **Gate local**: sempre WSL2 (`wsl -d Ubuntu -u root -- gestlog-gate`) — host
  Windows bloqueado pelo SAC (L-035); editar/patchear arquivos SEM cmdlets de
  conteúdo pwsh (L-050).
- **Convite**: aceite só cria CONTA NOVA — jamais redefine senha de e-mail
  registrado (takeover cross-tenant; L-048/ADR `ad-015-...`).
- **Rate limiter**: singleton em memória; ao escalar réplicas, trocar store
  (Redis) mantendo interface.
- **Modelos**: builders GLM pago; revisor DeepSeek; free tier só com confirmação
  (L-039).
- Regras detalhadas das sessões anteriores: ver ADRs em `docs/adr/` e
  `.opencode/LESSONS.md`.

## Próximos passos / bloqueios

1. **ÉPICO ATIVO `feat/seguranca-sweep`** (aprovado 2026-11-25): quitar C-1 +
   13 IMPORTANTES da varredura — 6 tasks, 1 PR cada contra a integração.
   Story aprovada; decisões das 8 open questions tomadas:
   (1) quota por empresa = coluna nullable c/ fallback ao settings global;
   (2) consumo histórico conta, sem reset; (3) `is_verified` nasce False
   (nenhuma rota exige verified — conferido); (4) duplicatas de e-mail:
   migração fail-fast p/ resolução manual; (5) `retention_days<=0`: rotina
   recusa purgar + CheckConstraint; (6) `fontes` divergente: filtra p/ tools
   realmente consultadas, nunca recusa turno; (7) sem `usage_metadata`:
   estimar `max(1, len//4)`, nunca 0; (8) resposta de convite sempre
   genérica, conflito só em log/auditoria.
   Achados LOW (CSRF token, pool_pre_ping, dedup ItemCorrecao, etc.) ficaram
   de fora (backlog). Relatório completo da varredura: 2 reviews
   `code-reviewer-agent` de 2026-11-25 (auth+web / dados+LLM) — C-1 quota
   inoperante é BLOCK.
2. **Roadmap registrado nas ADRs (futuro, não bloqueante)**: entrega do token
   por e-mail; aceite autenticado para vínculo de usuário existente; store
   Redis p/ rate limit em réplicas; `get_sync_session`→`web/deps.py`, remover
   TOOLS mock (STATE "Débitos técnicos herdados"); higiene do comando `/end`
   (ainda menciona o MCP graphify).
3. Decisões pendentes do autor: PDF `docs/business/KipperDev-...pdf` segue não
   rastreado; `.gitignore`/handoffs desta sessão ainda não commitados.
4. Docker Desktop precisa estar rodando para a matriz Postgres local (`docker
   start gestlog-pg`).
5. Sem bloqueios ativos.

## WIP local (não commitado)

- `M`: `.gitignore` (`.agents/` + `skills-lock.json`), `.opencode/CONTEXT.md`,
  `.opencode/LESSONS.md` (memória desta sessão — commitados pelo `/end`
  conforme fluxo anterior).
- `??`: `docs/business/KipperDev-Guia-Seguranca-Vibe-Coding.pdf` (não rastreado
  de propósito, decisão do autor).
- `.agents/skills/` e `skills-lock.json`: ignorados pelo git.
- Nota: `.venv` do repo ficou com binários Linux (WSL) — `uv sync --extra dev`
  no host se precisar do venv Windows.

## Artefatos do graphify

- **Graphify indisponível** — MCP removido da config no PR #78; ferramentas não
  presentes nesta sessão. Nós/arestas/comunidades: não verificado.
- `graphify-out/` LOCAL existe (grafo de 2026-09-21, commit `5845358f`) e é
  ignorado por design — não remover do `.gitignore` nem comitar.

## Documentos de projeto relevantes

- **Projeto**: `docs/specs/project/{PROJECT,ROADMAP,STATE}.md` — intocados nesta
  sessão (última alteração no PR #80).
- **Codebase**: `docs/specs/codebase/TESTING.md` (matriz Postgres; intocado).
- **Features**: `docs/specs/features/{f1-mvp,f2-hitl,ui-beautifului,relatorios-operacionais}/*`.
- **ADRs**: `docs/adr/` — nenhuma nova nesta sessão (últimas: `d1-remove-graphify`,
  `ad-019-historico-texto`, `ad-015-rate-limit-convite`, `empresa-ativa-cookie`).
- **Business**: `docs/business/PRD.md`; PDF KipperDev (não rastreado, intocado).
- **Config/skills**: `AGENTS.md`, `README.md`, `Makefile`, `opencode.json`
  (intocados); `.opencode/{agent,skills,plugin,command}/` intocados
  (`end.md` ainda menciona graphify — higiene futura); `.agents/skills/`
  (14 skills mattpocock podadas) e `skills-lock.json` — git-ignorados.
- **Skills do repo**: `.opencode/skills/{build-with-tests,code-reviewer,
  feature-factory,git-workflow,ship-feature,write-fluid-hybrid-adr}` — canônicas,
  intocadas.

---

# Histórico (sessões anteriores, resumido)

- **2026-11-06**: quitação D1–D7 via PRs #78 (D1, graphify removido),
  #79 (D2–D4: Text+índices, carimbo monotônico, botões SSE) e #80 (D5–D7:
  rate limit, convite só cria conta nova, empresa ativa, evals CI). Lições
  L-045..L-050. Self-review + ADR + code review independente por PR.
- **2026-10-28**: sessão de quitação D1–D7 trabalhada (código/testes/docs
  prontos; PRs ficaram para 2026-11-06). Allowlist do revisor validada.
- **2026-10-26**: endurecimento da allowlist do revisor em 4 rodadas de review do
  #77 (fuzzing real); L-043; PRs #76/#77 mergeados (config de modelos, catch-all
  deny no revisor, memória de sessão, ADR didático).
- **2026-10-22**: débito Postgres no CI (matriz de dialetos) — PR #74; code-reviewer
  desbloqueado (L-040); decisão "tudo pago" (L-039); self-reviews + ADRs.
- **2026-10-07**: AD-027 quitado (FKs de `user.id` → `GUID`, PR #73); APPROVE.
- **2026-10-06**: FU-2..FU-7 mergeados; gate local via WSL2 (Smart App Control).
- **2026-09-30**: relatórios operacionais (#66) + release v0.4.0 (#67); FU-1 (#68).
- **2026-09-18**: F1 completa (34/34) + release v0.1.0.
