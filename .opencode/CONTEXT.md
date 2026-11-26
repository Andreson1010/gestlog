# Contexto da Sessão — épico seguranca-sweep: fix de e-mail Unicode na T3 + review APPROVE do PR #83

> Handoff persistente. `/end` grava, `/start` lê. Última atualização: 2026-11-26.
> Branch: `feat/sec-t03-pii` · HEAD: `9ffbbee` · Integração: `feat/seguranca-sweep` @ `1cee0af`.

## Estado atual

- **gestlog**: multiagente LangGraph (supervisor + transporte/fornecedores/estoque),
  FastAPI + Jinja2/HTMX/SSE + Postgres (`empresa_id`) + FastAPI Users.
- `main` @ `2f3550e` (ahead 1 de origin). Tags `v0.1.0`..`v0.4.0`.
- **ÉPICO ATIVO `feat/seguranca-sweep`**: T1 (#81) e T2 (#82) mergeados;
  **T3 = PR #83 ABERTO** — code review independente concluído: **APPROVE**
  (0 CRITICAL/HIGH, 1 MEDIUM + 5 LOW). Falta decidir os consertos baratos e
  squash-merge. Depois: T5 → T4 → T6 → ACEITA.
- **Gates**: suite completa verde nesta sessão (2026-11-26): **661 passed,
  3 skipped, 99,10% cobertura** via `wsl -d Ubuntu` (L-057); black/ruff limpos.
  Postgres fica para o CI (docker daemon do host).
- **Modelos (tudo pago)**: builders/default `opencode-go/glm-5.3-flash`; revisor
  `code-reviewer-agent` em `opencode-go/deepseek-v4.1-flash`.
- **Harness de dev**: `http://127.0.0.1:8000` (login `demo@gestlog.local` /
  `demo12345`), `serve_dev.py` fora do repo.

## O que foi feito nesta sessão (2026-11-26) — CONCLUÍDO

- `/start` validou o handoff contra o repo — CONTEXT.md estava na sessão de
  skills (pré-épico); reescrito com o estado real do épico.
- **WIP vermelho diagnosticado**: `tests/privacy/test_redacao.py` parametrizado
  com `joão@empresa.com` falhava — `_EMAIL` ASCII-only; local-part acentuado
  era capturado como `[NOME]` (nome em `NOMES_COMUNS`) e vazava `@empresa.com`.
  Teste rodado via WSL para confirmar (1 failed, 25 passed).
- **Conserto (opção aprovada pelo autor)**: `_EMAIL` de
  `src/gestlog/privacy/redacao.py:39` → `\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b`
  (Unicode). Gate completo verde (661 passed, 99,10%). Commit `9ffbbee`
  (fix + teste) empurrado no PR #83.
- **Code review do PR #83** (`code-reviewer-agent`, DeepSeek): **APPROVE**.
  Achados: [MEDIUM] `update(Convite)` cru em `audit/retencao.py:46` fora da
  porta única db/repositories (já sancionado como débito no design/ADR —
  extrair `ConviteRepository.purgar_email` no futuro); [LOW] doc-drift em
  `design.md:290,310` (regex/assinatura antigas); [LOW] TLD IDN
  (`ana@empresa.рф`) ainda escapa — documentar como limitação; [LOW]
  docstrings/ADR superestimam testes de ordem CNPJ↔CPF (ordem real é
  discriminada por `test_telefone_sem_mascara...`); [LOW] `rowcount or 0`
  pode propagar -1 em `retencao.py:55` → `max(0, ...)`; [LOW] testes
  opcionais (exceção genérica propagando; isolamento cross-empresa).
- Nenhuma nova lição em LESSONS.md (deslizes da sessão já cobertos por
  L-034/L-055).

## Decisões e regras (não esquecer)

- **Gate local**: sempre WSL2 (`wsl -d Ubuntu bash -lc "cd /mnt/c/Users/ander/
  8_projetos/gestlog && uv run ..."` — caminho COM `/Users/`); host Windows
  bloqueado pelo SAC (L-035). `uv run` direto falha se o `.venv` estiver
  desatualizado — rodar `uv sync --extra dev` antes.
- **Git**: estado do working copy verificado pelo git do HOST — diff/stat do
  WSL em repo Windows é ruído CRLF em massa (L-055).
- **Editar arquivos** SEM cmdlets de conteúdo pwsh (L-050) — usar Read/Edit/Write.
- **Processo**: self-review → PR → code review independente → squash-merge;
  `main` nunca recebe push direto; feature-factory / ship-feature canônicos.
- **Convite**: aceite só cria CONTA NOVA — jamais redefine senha de e-mail
  registrado (takeover cross-tenant; L-048/ADR `ad-015-...`).
- **PII**: ordem de redação fixa EMAIL → CNPJ → CPF → TELEFONE → ENDERECO →
  CEP → NOME; redação acontece ANTES do LLM; teste discriminante por categoria.
- Regras detalhadas: ADRs em `docs/adr/` e `.opencode/LESSONS.md` (até L-057).

## Próximos passos / bloqueios

1. **PENDENTE — decisão do autor**: endereçar os achados baratos do review
   antes do merge (doc-drift do `design.md`, `max(0, rowcount)`, docstrings/ADR
   + nota de limitação TLD) ou merge direto com follow-ups registrados.
2. **Squash-merge do PR #83** contra `feat/seguranca-sweep` (após item 1).
3. **Ordem do épico**: T5 (histórico, migração 4) → T4 (fontes, sem migração)
   → T6 (config/rede, sem migração) → ACEITA (bateria final). Detalhes e
   checklists em `docs/specs/features/seguranca-sweep/tasks.md` (T1–T3 `[x]`).
4. **Backlog do épico**: achados LOW da varredura (CSRF token, pool_pre_ping,
   dedup ItemCorrecao etc.) + débito `ConviteRepository.purgar_email` + TLD IDN.
5. Docker Desktop precisa estar rodando para a matriz Postgres local (`docker
   start gestlog-pg`).

## WIP local (não commitado)

- `M`: `.opencode/CONTEXT.md` (este handoff — commitado pelo `/end`).
- `??`: `docs/business/KipperDev-Guia-Seguranca-Vibe-Coding.pdf` (não rastreado
  de propósito, decisão do autor).
- `.agents/skills/` e `skills-lock.json`: ignorados pelo git.

## Artefatos do graphify

- **Graphify indisponível** — MCP removido da config no PR #78; ferramentas não
  presentes nesta sessão. Nós/arestas/comunidades: não verificado.
- `graphify-out/` LOCAL existe (grafo de 2026-09-21, commit `5845358f`) e é
  ignorado por design — não remover do `.gitignore` nem comitar.

## Documentos de projeto relevantes

- **Épico**: `docs/specs/features/seguranca-sweep/{spec,design,tasks}.md` —
  tasks.md com T1–T3 `[x]`; design.md com doc-drift LOW pendente (linhas 290/310).
- **ADRs desta task**: `docs/adr/seguranca-sweep-t{1,2,3}-*-self-review.md`.
- **Projeto**: `docs/specs/project/{PROJECT,ROADMAP,STATE}.md`.
- **Codebase**: `docs/specs/codebase/TESTING.md` (matriz Postgres).
- **Memória**: `.opencode/LESSONS.md` (até L-057, consolidada).
- **Config**: `AGENTS.md`, `README.md`, `Makefile`, `opencode.json` (intocados
  nesta sessão); `.opencode/skills/{build-with-tests,code-reviewer,
  feature-factory,git-workflow,ship-feature,write-fluid-hybrid-adr}` canônicas.
- **Código tocado**: `src/gestlog/privacy/redacao.py`, `tests/privacy/test_redacao.py`.

---

# Histórico (sessões anteriores, resumido)

- **2026-11-25/26 (épico T1–T3)**: T1 quota/metering (PR #81) e T2 identidade
  (PR #82) mergeados; T3 PII/LGPD commitado na task branch (redação PII,
  purga de convites, fail-safe retention, migração `f3c4d5e6f7a8`). ADRs de
  self-review + LESSONS até L-057 (L-052 downgrade pai, L-053 stash/restore,
  L-054 tool call fake canônica, L-055 diff cross-EOL, L-056 IntegrityError em
  rotas, L-057 `wsl -d Ubuntu` explícito).
- **2026-11-25 (skills)**: skills mattpocock 39→14 em `.agents/skills/`
  (git-ignoradas); L-051; commit `2f3550e` em `main`.
- **2026-11-06**: quitação D1–D7 via PRs #78/#79/#80. Lições L-045..L-050.
- **2026-10-26**: endurecimento da allowlist do revisor (#77); L-043.
- **2026-10-22**: débito Postgres no CI (matriz de dialetos, PR #74); L-040/L-039.
- **2026-10-07**: AD-027 quitado (FKs de `user.id` → GUID, PR #73).
- **2026-09-30**: relatórios operacionais (#66) + release v0.4.0 (#67); FU-1 (#68).
- **2026-09-18**: F1 completa (34/34) + release v0.1.0.
