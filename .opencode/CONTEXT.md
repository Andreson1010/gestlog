# Contexto da Sessão — F1 do gestlog: T21–T23 mergeadas, T24 pendente

> Handoff persistente. `/end` grava, `/start` lê. Última atualização: 2026-09-17.
> Branch: `feat/f1-mvp` (integração) · HEAD: `e05e77b` (este handoff é um commit
> docs no topo; o último commit de **código** é `5bcac81`, T23)

## Estado atual

- **gestlog**: fluxo multiagente em LangGraph (supervisor + especialistas
  transporte / fornecedores / estoque) com tools `@tool`. Remote `origin` =
  https://github.com/Andreson1010/gestlog (privado).
- **F1 (MVP) na integração `feat/f1-mvp`**: **T1–T23 + T34 CONCLUÍDOS** (24 de 34
  tasks); **10 PENDENTES (T24–T33)** — `docs/specs/features/f1-mvp/tasks.md`.
- Stack travado (AD-007): FastAPI + Jinja2/HTMX/SSE + Postgres (`empresa_id`) +
  FastAPI Users. Modelo de entrega (AD-016): `main` verde, `feat/f1-mvp` é a
  integração, **1 PR por task** com CI + self-review + `code-reviewer`; release
  único `feat/f1-mvp → main` + tag `v0.1.0`.
- **CI**: `.github/workflows/ci.yml` (na `main`, `f639f36`) — `black --check`,
  `ruff check`, `pytest` (gate 80%) em PRs e push. CI da T23 (PR #24) verde em 30s.
- **Suíte**: **157 testes, 97,76% de cobertura** (`uv run pytest`); Python 3.14.3
  no `.venv` (projeto exige `>=3.11`). *(não re-verificado neste `/end`; número da
  última execução da T23: 157 passed, 97,76%)*
- `main` = `f639f36`; `feat/f1-mvp` = `e05e77b` (= `origin/feat/f1-mvp`, **em
  sincronia**). **Árvore limpa; nenhum stash; nenhum PR aberto; nenhuma branch de
  task** (refs remotas de T21–T23 podadas).
- **Última task concluída — T23** (ver *O que foi feito*): UI de feedback (fontes +
  botões HTMX), PR #24, squash `5bcac81`, ADR `docs/adr/t23-feedback-ui-self-review.md`.

## O que foi feito nesta sessão (2026-09-17)

1. **T21 — Extração de recomendação, fontes e insuficiência** (PR #22, squash
   `88f5b38`). Mecanismo aprovado: a **tool comum vira passo terminal** do
   especialista — `create_specialist_node` detecta `enviar_resposta_logistica`
   (só quando é a única chamada do passo), devolve o texto composto e grava
   `dominio` no `AgentState`. `Recomendacao` + `extrair_recomendacao` em
   `copilot/service.py`; **fontes vazias ⇒ `MENSAGEM_INSUFICIENCIA`** (não
   persiste `Recommendation`). `enviar_resposta_logistica` ganhou `justificativa`
   opcional (supersede T34, aditivo). ADR `t21-...-self-review.md`.
2. **T22 — Feedback aceitar/descartar** (PR #23, squash `0dfc1dc`).
   `POST /recomendacoes/{id}/feedback` (form, `DecisaoFeedback` Literal);
   `RecommendationRepository.get_do_usuario` autoriza por **empresa + usuário**
   (senão **404**, sem vazar existência); `Feedback` append-only. CSRF mitigado
   por cookie `SameSite=lax`. ADR `t22-...-self-review.md`.
3. **T23 — UI de feedback** (PR #24, squash `5bcac81`). **Pareamento na leitura,
   sem migration**: `Turno` ganhou `recomendacao_id`/`fontes`/`decisao`;
   `_montar_turnos` intercala mensagens e recomendações por `(created_at, tipo,
   id)` (`tipo` antes do `id` para não depender de UUID aleatório em empates).
   `FeedbackRepository.latest_by_conversation` (última decisão vence). O endpoint
   passa a devolver **fragmento HTML** (`_feedback.html`) para swap HTMX;
   `chat.html` exibe `Fontes:` + botões. Self-review achou MEDIUM real (desempate)
   e corrigiu + teste. ADR `t23-...-self-review.md`.
4. **Docs**: `STATE.md` com **AD-017** (T21), **AD-018** (T22), **AD-019** (T23);
   `tasks.md` com progresso até T23; handoffs `c016131`/`87cc0ab`/`19e72c5`/
   `43f0bd9`/`bfef8d3`/`d30fed3` e correção de HEAD `e05e77b`.
5. **Fluxo**: todas as tasks seguiram build → **self-review (ADR)** → gate
   (`pytest`+`black`+`ruff`) → commit PT → PR → **code review** → squash. Code
   review: **0 CRITICAL/HIGH** nas três tasks.

## Decisões e regras (não esquecer)

- **Skills/agentes do `.opencode/` são agnósticos**; especificidades no `AGENTS.md`.
- **ADRs** com a skill `write-fluid-hybrid-adr` (5 seções: Contexto / Decisões /
  Concessões / Roadmap / Validação), arquivo `docs/adr/<slug>-self-review.md`.
- `uv run pytest` já ativa o gate de 80%; use `--no-cov` em execuções focadas.
  Nenhum teste toca rede/Ollama (`fake_model_cls` em `tests/conftest.py`).
- **Ambiente Windows**: App Control bloqueia os `.exe` do `.venv` e a DLL
  `_uuid_utils` (plugin `langsmith`). Rodar com `uv run python -m black|ruff` e
  `uv run python -m pytest -p no:langsmith`.
- **Nomes de código em português** (AD-008): `Empresa`/`empresa_id`. **Docs-as-code**
  (AD-011); **pacote único** com fronteiras `apps → agents → libs` (AD-012).
- **AD-014**: `AMBIENTE=prod` exige `AUTH_SECRET` (>= 32). **AD-015**: rate limiting
  e convite por token adiados. **AD-016**: épico + 1 PR/task; sem force-push.
- **Tools do tenant (T17)**: builders aceitam `tools` opcional (default = mock);
  `COMMON_TOOLS` sempre anexada; `specialist_tools` indexa por nome do especialista.
  Mock `TOOLS` é fallback do REPL (`cli.py`).
- **SSE (T18) / UI (T19)**: resposta final em eventos (`resposta`+`fim`); página
  `GET /chat` (303 sem sessão) separada do fragmento; resposta como `textContent`
  (anti-XSS); `sse-close="fim"`.
- **Histórico (T20)**: exibição, nunca realimentado no grafo. Débitos: falta
  `UniqueConstraint(empresa_id, user_id)`; `String(4000)` por mensagem; ordenação
  por `created_at, id`.
- **Recomendação (T21)**: só é recomendação se vier da tool comum; sem fonte vira
  insuficiência (não persiste). Parser lê o formato próprio da tool.
- **Feedback (T22)**: grava só após autorizar por empresa+usuário; **404** sem
  vazar existência; append-only (KPI usa a **última** decisão).
- **UI de feedback (T23)**: pareamento recomendação↔turno **na leitura** (sem
  migration); empates por `tipo`, nunca por UUID; endpoint devolve fragmento HTML.
- **Fluxo da task**: `feat/f1-tXX-*` de `feat/f1-mvp` → build-with-tests →
  **self-review (developer-self-reviewer + ADR)** → gate → commit `feat(f1): ...` →
  PR contra `feat/f1-mvp` → **code review** → squash + apagar branch.

## Próximos passos / bloqueios

1. **T24 — PENDENTE (próxima ação)**: **Módulo de redação de PII** — `redact(text)`
   que remove/minimiza nomes, endereços e telefones antes do LLM. Where
   `src/gestlog/privacy/`; depends T1; **testes unit**. Requirement SEC-01. Done
   when: casos de nome/endereço/telefone redigidos; texto sem PII intacto. Par
   T24/T25 (T25 integra no copiloto). Branch `feat/f1-t24-*` → PR contra `feat/f1-mvp`.
2. **T25–T33** seguem (integrar PII, auditoria/retenção, uso/quota, golden set,
   admin, KPIs, aceitação P1).
3. **Débito T23**: turno ao vivo (SSE) ainda não recebe botões — a decisão só
   aparece ao recarregar o histórico; emitir `event: fontes`/fragmento e ordenação
   monotônica de mensagens (substituir pareamento por `created_at`) fica futuro.
4. **Débitos T20**: `UniqueConstraint(empresa_id, user_id)`; reavaliar
   `String(4000)`/`Text`; mover `get_sync_session` de `ingestion_ui.py` para
   `web/deps.py`.
5. **Pendência pós-T17**: remover `TOOLS` mock do REPL quando a CLI ganhar banco.
6. Ao fechar a F1: PR de release `feat/f1-mvp → main` + tag `v0.1.0`.
7. Opcional: remover backups locais `backup/f1-fase2`/`backup/f1-mvp`; avaliar o
   plugin `@opencode-ai/plugin` em `.opencode/`.

## WIP local (não commitado)

- **Nenhum.** Árvore limpa. `feat/f1-mvp` sincronizada com `origin/feat/f1-mvp` na
  correção de HEAD `e05e77b`; sem stash e sem PR aberto.

## Artefatos do graphify

- **graphify indisponível para o gestlog.** `graphify_graph_stats` retornou
  `graph.json not found: C:\Users\ander\8_projetos\gestlog\graphify-out\graph.json`
  (`Test-Path graphify-out/graph.json` = `False`). O `opencode.json` aponta o MCP
  para `C:\Users\ander\8_projetos\medasist\graphify-out\graph.json` (OUTRO repo) —
  **não representa o gestlog**. **Nenhum número registrado (não verificado); não
  inventar valores.**
- Módulos tocados nesta sessão: `src/gestlog/{copilot,agents,tools,repositories,web}/`
  e `state.py`; docs em `docs/adr/` e `docs/specs/`. Comunidades afetadas:
  **não verificado** (sem grafo do gestlog).

## Documentos de projeto relevantes

- `AGENTS.md` — arquitetura, convenções, comandos e fluxo épico+task.
- `README.md`, `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`.
- `docs/business/PRD.md`.
- `docs/specs/project/{PROJECT,ROADMAP,STATE}.md` — TLC; decisões AD-001..AD-019.
- `docs/specs/features/f1-mvp/{spec,design,tasks}.md` — F1 (`tasks.md`: 34 tasks;
  T1–T23 e T34 concluídos).
- `docs/specs/codebase/TESTING.md` — matriz de testes e gates.
- `docs/adr/` — self-reviews **fluid-hybrid** (sufixo `-self-review`): `t13` a
  `t23` + `t34` (12 arquivos).
- `src/gestlog/`: `config.py`, `llm.py`, `graph.py`, `state.py`, `cli.py`,
  `agents/` (base detecta tool comum terminal; `dominio` no estado), `tools/`
  (`common.py` = tool comum + rótulos), `db/`, `repositories/`
  (`conversations.py` = conversas/mensagens/recomendações/feedback), `auth/`,
  `web/` (`chat.py` SSE; `chat_ui.py` UI; `feedback.py` T22/T23; `templates/`),
  `copilot/` (`service.py` = `Recomendacao`/`extrair_recomendacao`/`Turno`),
  `ingestion/`.
- `.opencode/skills/` — build-with-tests, code-reviewer, feature-factory,
  git-workflow, ship-feature, write-fluid-hybrid-adr.
- `.opencode/agent/` — backend-builder, codebase-researcher,
  developer-self-reviewer, frontend-builder, persistence-checker, spec-writer,
  story-writer, test-verifier, validator.
- `.opencode/command/` — start, end, explain, run-tests.

---

# Histórico (sessões anteriores, resumido)

- **2026-09-17 (esta):** **T21** (PR #22, `88f5b38`), **T22** (PR #23, `0dfc1dc`) e
  **T23** (PR #24, `5bcac81`) concluídas e mergeadas; `STATE.md` ganhou AD-017/018/019;
  139→157 testes (97,58%→97,76%). F1 retoma na **T24**.
- **2026-09-17 (anterior):** **T20 concluída e mergeada** (PR #21, `0ab9e03` —
  persistência/histórico por usuário e empresa, ADR `t20-historico-conversa-self-review`).
- **2026-09-16:** skill `write-fluid-hybrid-adr` criada; **T19 mergeada** (PR #20,
  `450df94` — UI do chat HTMX/SSE); ADRs t13–t18/t34 refeitas no formato fluid-hybrid.
- **2026-09-15:** T15 (`a5fbcfe`), T16 (`2387a0e`), T34 (`ebf185e`), T17 (`6599c5c`),
  T18 (`61172a5`) concluídas e mergeadas; 109→125 testes.
- **2026-09-15 (anterior):** T14 concluído e mergeado (PR #14, `12c046f`).
- **2026-09-14:** T13 (PR #13, `fcd93fc`) e T12 (PR #12, `224f918`); fase 5.5 de
  self-review/ADR adicionada ao pipeline (`2443b92`).
- **2026-09-13:** code review dos PRs stacked (AD-014/015); fluxo épico + 1 PR/task
  com CI (AD-016); T10 (PR #6) e T11 (PR #8).
- **2026-09-12:** catálogo de tools (AD-010); docs-as-code (AD-011); fronteiras do
  pacote (AD-012); auth async (AD-013); T6–T9.
- **2026-09-11:** scaffold `.opencode/`; PRD + TLC; F1 planejada; rename
  `Tenant`→`Empresa`.
