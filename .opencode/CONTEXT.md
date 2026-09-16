# Contexto da Sessão — F1 do gestlog: T15–T19 + T34 mergeadas, T20 pendente

> Handoff persistente. `/end` grava, `/start` lê. Última atualização: 2026-09-16.
> Branch: `feat/f1-mvp` (integração) · HEAD: `450df94`

## Estado atual

- **gestlog**: fluxo multiagente em LangGraph (supervisor + especialistas
  transporte / fornecedores / estoque) com tools `@tool`. Remote `origin` =
  https://github.com/Andreson1010/gestlog (privado).
- **F1 (MVP) em execução** na branch de integração `feat/f1-mvp`: **T1–T19 + T34
  CONCLUÍDOS**; **14 tasks PENDENTES (T20–T33)** — `docs/specs/features/f1-mvp/tasks.md`
  (34 tasks no total).
- Stack travado (AD-007): FastAPI + Jinja2/HTMX/SSE + Postgres (`empresa_id`) +
  FastAPI Users.
- **Modelo de entrega (AD-016)**: `main` verde com CI; `feat/f1-mvp` é a branch de
  integração; **1 PR por task** (`feat/f1-tXX-*` → `feat/f1-mvp`) com CI +
  self-review + `code-reviewer`; release único `feat/f1-mvp → main` + tag `v0.1.0`.
- **CI**: `.github/workflows/ci.yml` (na `main`, `f639f36`) — `black --check`,
  `ruff check`, `pytest` (gate 80%) em PRs e push para `main`/`feat/f1-mvp`.
- **Suíte**: **131 testes, 97,48% de cobertura** (`uv run pytest`); Python 3.14.3
  no `.venv` (projeto exige `>=3.11`).
- **Estrutura**: `src/gestlog/` (`config`, `llm`, `state`, `graph`, `cli`,
  `agents/`, `tools/`, `db/`, `repositories/`, `auth/`, `web/`, `ingestion/`,
  **`copilot/`**), `alembic/`, `docs/adr/`, `tests/` espelhando `src/`.
- Árvore de trabalho **limpa**; nenhum PR aberto. Skill `write-fluid-hybrid-adr`
  commitada (absorvida no squash `450df94`).

## O que foi feito nesta sessão

Entrega da **T15 → T16 → T34 → T17 → T18 → T19** (uma branch + PR por task, squash
na `feat/f1-mvp`), cada uma com self-review (`developer-self-reviewer` + ADR) e code
review antes do merge:

- **T15** (PR #15, squash `a5fbcfe`): tools de fornecedores por tenant em
  `tools/suppliers.py` + `tratar_conformidade` read-only (inativo, nota < 4.0,
  prazo > 15d); fábrica `build_supplier_tools`. ADR `t15-supplier-tools`.
- **T16** (PR #16, squash `2387a0e`): tools de transporte por tenant em
  `tools/transport.py` + `otimizar_entrega` read-only; `calcular_frete`/`prazo`
  mantêm o cálculo (helpers compartilhados); fábrica `build_transport_tools`.
  ADR `t16-transport-tools`.
- **T34** (PR #17, squash `ebf185e`): tool comum `enviar_resposta_logistica` em
  `tools/common.py` (`COMMON_TOOLS`), anexada aos 3 especialistas. ADR
  `t34-common-response`.
- **T17** (PR #18, squash `6599c5c`): **Copilot Service** em `copilot/service.py`
  (`CopilotService.tools_por_dominio()` + `answer()`); seam de injeção
  `build_graph(..., specialist_tools=...)` e 3º parâmetro `tools` nos builders.
  ADR `t17-copilot-service` (resolve `settings` uma vez; corrige ponteiro
  T19→T17 nas ADRs T14/T15/T16/T34 e docstrings).
- **T18** (PR #19, squash `61172a5`): **endpoint SSE de chat** em `web/chat.py`
  (`GET /chat/stream?pergunta=`, 401 sem sessão, 422 vazio; eventos `resposta` +
  `fim`); registrado em `web/app.py`. ADR `t18-chat-sse`.
- **T19** (PR #20, squash `450df94`): **UI do chat (HTMX/SSE)** em
  `web/chat_ui.py` (`GET /chat` página → 303 sem sessão; `GET /chat/pergunta`
  fragmento) + `templates/chat.html`/`chat_turno.html` (formulário HTMX
  `hx-get`/`beforeend`; turno com `sse-connect`/`sse-swap`) + extensão
  `htmx-ext-sse@2.2.2` com SRI em `base.html`. ADR `t19-chat-ui`. Self-review
  corrigiu XSS (`hx-swap="textContent"`) e reconexão (`sse-close="fim"`);
  6 testes de integração.
- **Handoff/limpeza**: skill `write-fluid-hybrid-adr` (ADR narrativa fluid-hybrid,
  usada na fase 5.5 do `feature-factory`), handoffs e correção de HEAD; o squash
  do PR #20 absorveu os commits locais de skill/handoff (nada perdido).
- `AGENTS.md`: documentado o parâmetro `specialist_tools` do `build_graph`.

## Decisões e regras (não esquecer)

- **Skills/agentes do `.opencode/` são agnósticos**; especificidades do projeto
  ficam no `AGENTS.md`.
- `uv run pytest` já ativa o gate de 80% (`addopts`); use `--no-cov` em execuções
  focadas. Nenhum teste toca rede/Ollama (`fake_model_cls` em `tests/conftest.py`).
- **Nomes de código em português** (AD-008): `Empresa`/`empresa_id` ("tenant" só
  nos docs).
- **Docs-as-code** (AD-011); **pacote único** com fronteiras `apps → agents →
  libs` (AD-012). Endpoint/web → `apps`; nó/tool/grafo → `agents`; modelo/repo/
  config → `libs`.
- **Produto**: SaaS multi-cliente, read-only no MVP, HITL na F2, importação→API,
  LLM hospedado, LGPD/PII (AD-001..006).
- **AD-014**: `AMBIENTE=prod` exige `AUTH_SECRET` (>= 32 chars). **AD-015**: rate
  limiting/convite por token adiados. **AD-016**: épico + 1 PR/task, proibido
  force-push em `main`/`feat/f1-mvp`.
- **Injeção de tools do tenant (T17)**: builders aceitam `tools` opcional
  (default = mock `TOOLS`); `COMMON_TOOLS` é **sempre** anexada no builder;
  `build_graph(..., specialist_tools=)` indexa por nome do especialista. O mock
  `TOOLS` permanece como fallback do REPL (`cli.py`).
- **Chat SSE (T18)**: resposta final em eventos (`resposta` + `fim`), não token a
  token (pergunta aberta 4 do design); rota `GET` (compatível com HTMX
  `sse-connect`/EventSource); **401** (endpoint de API), não redirect.
- **Chat UI (T19)**: `GET /chat` (página, 303 sem sessão) separa `GET /chat/pergunta`
  (fragmento HTMX anexado com `beforeend`); resposta via `sse-connect` +
  `hx-swap="textContent"` (anti-XSS do payload do LLM) e `sse-close="fim"`
  (encerra o EventSource, evita reexecutar o grafo); extensão SSE global em
  `base.html` com SRI.
- **Fluxo da task**: cortar `feat/f1-tXX-*` de `feat/f1-mvp` → implementar
  (`build-with-tests`) → gate (`pytest` + `black` + `ruff`) → commit PT
  `feat(f1): ...` → PR contra `feat/f1-mvp` → **self-review obrigatório** (ADR em
  `docs/adr/<slug>-self-review.md`) → **code review** (`code-reviewer`) → squash +
  apagar branch.

## Próximos passos / bloqueios

1. **T20 — PENDENTE** (próxima ação): **Persistência e histórico da conversa** —
   gravar conversa/mensagens por usuário/tenant e exibir histórico ao voltar.
   Where `src/gestlog/copilot/`, `src/gestlog/web/`; depends T18; reuses T5.
   Done when: recarregar mantém o histórico no tenant correto. Branch
   `feat/f1-t20-*` → PR contra `feat/f1-mvp`.
2. T21–T33 seguem a T20 (recomendação/fontes, feedback aceitar/descartar,
   PII/auditoria/uso…).
3. Ao fechar a F1: PR de release `feat/f1-mvp → main` + tag `v0.1.0`.
4. Pendência técnica (pós-T17): os `TOOLS` mock ainda são fallback do REPL; DB no
   CLI/remoção do mock quando não houver mais uso.
5. Opcional: remover backups locais `backup/f1-fase2` e `backup/f1-mvp` (sem uso).
6. Opcional: avaliar o plugin `@opencode-ai/plugin` em `.opencode/` (`node_modules`
   não foi copiado).

## WIP local (não commitado)

- **Nenhum** (exceto este handoff). A skill `write-fluid-hybrid-adr` + ajuste do
  `feature-factory` estão no squash `450df94`.
- `main` = `f639f36`; `feat/f1-mvp` = `450df94`; **nenhum PR aberto**. Branch
  `feat/f1-t19-chat-ui` apagada (local e remoto). Backups locais `backup/f1-fase2`
  e `backup/f1-mvp` ainda existem.

## Artefatos do graphify

- **graphify indisponível para o gestlog**: `graphify_graph_stats` retornou
  `graph.json not found: C:\Users\ander\8_projetos\gestlog\graphify-out\graph.json`
  (`Test-Path graphify-out/graph.json` = `False`). O MCP existe, mas o
  `opencode.json:14` aponta para `C:\Users\ander\8_projetos\medasist\graphify-out\graph.json`
  (OUTRO repositório) — **não representa o gestlog**. Nenhum número registrado.
- God nodes / comunidades afetadas: **não verificado** (sem grafo do gestlog).

## Documentos de projeto relevantes

- `AGENTS.md` — arquitetura, convenções, comandos e fluxo épico+task (atualizado:
  `build_graph(..., specialist_tools=)`).
- `docs/business/PRD.md`.
- `docs/specs/project/{PROJECT,ROADMAP,STATE}.md` — TLC; decisões AD-001..AD-016.
- `docs/specs/features/f1-mvp/{spec,design,tasks}.md` — planejamento da F1
  (`tasks.md`: 34 tasks; T1–T19 e T34 concluídos).
- `docs/specs/codebase/TESTING.md` — matriz de testes e gates.
- `docs/adr/` — self-reviews: `t13-upload-ui`, `t14-inventory-tools`,
  `t15-supplier-tools`, `t16-transport-tools`, `t34-common-response`,
  `t17-copilot-service`, `t18-chat-sse`, `t19-chat-ui`.
- `README.md`, `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`.
- `src/gestlog/config.py` (`Settings`/`get_settings`), `src/gestlog/llm.py`
  (`build_chat_model`), `src/gestlog/graph.py` (`build_graph`/`run_query`),
  `src/gestlog/copilot/`, `src/gestlog/web/chat.py` (SSE T18),
  `src/gestlog/web/chat_ui.py` (UI T19), `src/gestlog/web/templates/chat*.html`,
  `tests/conftest.py` (`FakeChatModel`/`fake_model_cls`).
- `.opencode/skills/` — build-with-tests, code-reviewer, feature-factory,
  git-workflow, ship-feature, **write-fluid-hybrid-adr**.
- `.opencode/agent/` — backend-builder, codebase-researcher,
  developer-self-reviewer, frontend-builder, persistence-checker, spec-writer,
  story-writer, test-verifier, validator.
- `.opencode/command/` — start, end, explain, run-tests.

---

# Histórico (sessões anteriores, resumido)

- **2026-09-16:** handoff validado/corrigido; skill `write-fluid-hybrid-adr`
  adicionada; **T19 concluída e mergeada** (PR #20, squash `450df94` — UI do chat
  HTMX/SSE, ADR `t19-chat-ui`); 125→131 testes (97,43%→97,48%). Árvore limpa; F1
  retoma na T20.
- **2026-09-15:** T15 (`a5fbcfe`), T16 (`2387a0e`), T34
  (`ebf185e`), T17 (`6599c5c`), T18 (`61172a5`) concluídas e mergeadas; 109→125
  testes (97,06%→97,43%); ADRs t15/t16/t34/t17/t18; handoff validado/corrigido.
- **2026-09-15 (anterior):** T14 concluído e mergeado (PR #14, `12c046f`) — tools
  de estoque por tenant + análises read-only; ADR `t14-inventory-tools`; suíte
  103/96,93%; `tasks.md` corrigido (T13/T14).
- **2026-09-14:** T13 (PR #13, `fcd93fc`, UI HTMX de upload/histórico) e T12
  (PR #12, `224f918`, serviço de importação/status); fase 5.5 de self-review/ADR
  adicionada ao pipeline (`2443b92`).
- **2026-09-13:** code review dos PRs stacked + correções (AD-014/015); fluxo
  épico + 1 PR/task com CI (AD-016); T10 (PR #6) e T11 (PR #8).
- **2026-09-12:** catálogo de tools (AD-010); docs-as-code (AD-011); fronteiras do
  pacote (AD-012); auth async (AD-013); T6–T9.
- **2026-09-11:** scaffold `.opencode/`; PRD + TLC; F1 planejada; rename
  `Tenant`→`Empresa`.
