# Contexto da Sessão — F1 do gestlog: T21 mergeada, T22 pendente

> Handoff persistente. `/end` grava, `/start` lê. Última atualização: 2026-09-17.
> Branch: `feat/f1-mvp` (integração) · HEAD: `88f5b38`

## Estado atual

- **gestlog**: fluxo multiagente em LangGraph (supervisor + especialistas
  transporte / fornecedores / estoque) com tools `@tool`. Remote `origin` =
  https://github.com/Andreson1010/gestlog (privado).
- **F1 (MVP) na branch de integração `feat/f1-mvp`**: **T1–T21 + T34 CONCLUÍDOS**
  (22 de 34 tasks); **12 PENDENTES (T22–T33)** —
  `docs/specs/features/f1-mvp/tasks.md`.
- Stack travado (AD-007): FastAPI + Jinja2/HTMX/SSE + Postgres (`empresa_id`) +
  FastAPI Users.
- **Modelo de entrega (AD-016)**: `main` verde com CI; `feat/f1-mvp` é a
  integração; **1 PR por task** (`feat/f1-tXX-*` → `feat/f1-mvp`) com CI +
  self-review + `code-reviewer`; release único `feat/f1-mvp → main` + tag
  `v0.1.0`.
- **CI**: `.github/workflows/ci.yml` (na `main`, `f639f36`) — `black --check`,
  `ruff check`, `pytest` (gate 80%) em PRs e push para `main`/`feat/f1-mvp`.
  CI da T21 (PR #22) verde em 39s.
- **Suíte**: **147 testes, 97,68% de cobertura** (`uv run pytest`); Python 3.14.3
  no `.venv` (projeto exige `>=3.11`).
- `main` = `f639f36`; `feat/f1-mvp` = `88f5b38` (= `origin/feat/f1-mvp`, **em
  sincronia**). **Árvore limpa; nenhum stash; nenhum PR aberto; nenhuma branch de
  task pendente** (a de T21 foi apagada no remoto e localmente).
- **T21 concluída** (ver *O que foi feito*): recomendação + justificativa + fontes
  e insuficiência (COP-03/COP-04), PR #22, squash `88f5b38`, ADR
  `docs/adr/t21-recomendacao-fontes-insuficiencia-self-review.md`.

## O que foi feito nesta sessão (2026-09-17)

1. **Handoff de entrada validado/corrigido**: o arquivo apontava HEAD `ba477ae`,
   mas o handoff já estava commitado em `b877eeb`; corrigido (`c016131`).
2. **T20 — Persistência e histórico da conversa — CONCLUÍDA E MERGEADA**
   (PR #21, squash `0ab9e03`):
   - `ConversationRepository.get_by_user`/`get_or_create`: **uma** conversa por
     par `(empresa_id, user_id)`.
   - `CopilotService` passou a exigir `user_id` e persiste o turno via
     `registrar_turno` (pergunta `"user"` + resposta `"assistant"` em um commit).
   - `Turno` + `carregar_historico`/`_montar_turnos` em `copilot/service.py`.
   - `GET /chat` renderiza o histórico via Jinja (autoescape); `GET /chat/stream`
     injeta `user_id`.
   - Nova dep `get_current_empresa_optional` (+ `_buscar_membership` extraída):
     página segue 303 → `/login`; API segue 401.
   - 8 testes novos (isolamento por empresa e por usuário, unidade + integração).
   - Self-review `developer-self-reviewer`: **APPROVE**; corrigiu ordenação sem
     desempate e cobriu turno órfão. Code review: **0 CRITICAL/HIGH**.
3. **T21 — Extração de recomendação, fontes e insuficiência — CONCLUÍDA E
   MERGEADA** (PR #22, squash `88f5b38`), na ordem corrigida
   build→self-review→gate→commit→PR→code review:
   - Mecanismo (aprovado): a **tool comum vira passo terminal** do especialista.
     `create_specialist_node` detecta `enviar_resposta_logistica` e, **só quando é
     a única chamada do passo**, executa, devolve o texto composto como
     `AIMessage` final e grava `dominio` no `AgentState` (novo campo).
   - `Recomendacao(dominio, texto, justificativa, fontes, insuficiente)` +
     `extrair_recomendacao` no `copilot/service.py`; rótulos compartilhados com
     `tools/common.py` (`ROTULO_*`, `FONTES_VAZIAS`, `NOME_TOOL_RESPOSTA`).
   - `enviar_resposta_logistica` ganhou `justificativa: str = ""` opcional
     (supersede a assinatura da T34, de forma aditiva/retrocompatível);
     `INSTRUCAO_RESPOSTA` orienta os 3 prompts.
   - **Fontes vazias ⇒ insuficiência** (`MENSAGEM_INSUFICIENCIA`), sem alucinar;
     `Recommendation` só é persistida quando há base; fora de escopo preservado.
   - Self-review APPROVE + ADR; code review achou 1 MEDIUM (tool comum em lote
     encerrando cedo) → **corrigido** (`9998b6a`) com guarda de chamada única + teste.
   - 147 testes (139→147), 97,68%; `copilot/service.py`, `tools/common.py`,
     `state.py` em 100%.
4. **Handoffs/correções**: `cc49bb4`/`4662bf1` (T20); `87cc0ab` e `88f5b38`
   (ordem do fluxo + T21).
5. **Investigação respondida**: a comunicação **entre agentes é sync** e via
   estado compartilhado (`AgentState.messages`), não mensagens diretas —
   `graph.invoke` (`graph.py:100`), nós síncronos (`agents/base.py:44`), tools
   `.invoke`; supervisor roteia para 1 especialista por vez, sem paralelismo.
   Auth/DB são async (AD-013); o SSE emite a resposta final de uma vez.

## Decisões e regras (não esquecer)

- **Skills/agentes do `.opencode/` são agnósticos**; especificidades do projeto
  ficam no `AGENTS.md`.
- **ADRs**: usar a skill `write-fluid-hybrid-adr` (narrativa única, 5 seções
  fixas: Contexto/Decisões/Concessões/Roadmap/Validação), arquivo
  `docs/adr/<slug>-self-review.md`.
- `uv run pytest` já ativa o gate de 80% (`addopts`); use `--no-cov` em execuções
  focadas. Nenhum teste toca rede/Ollama (`fake_model_cls` em `tests/conftest.py`).
- **Nomes de código em português** (AD-008): `Empresa`/`empresa_id` ("tenant" só
  nos docs).
- **Docs-as-code** (AD-011); **pacote único** com fronteiras `apps → agents →
  libs` (AD-012). Endpoint/web → `apps`; nó/tool/grafo → `agents`; modelo/repo/
  config → `libs`.
- **AD-014**: `AMBIENTE=prod` exige `AUTH_SECRET` (>= 32 chars). **AD-015**: rate
  limiting/convite por token adiados. **AD-016**: épico + 1 PR/task; proibido
  force-push em `main`/`feat/f1-mvp`.
- **Injeção de tools do tenant (T17)**: builders aceitam `tools` opcional (default
  = mock `TOOLS`); `COMMON_TOOLS` é **sempre** anexada; `build_graph(...,
  specialist_tools=)` indexa por nome do especialista. Mock `TOOLS` é fallback do
  REPL (`cli.py`).
- **Chat SSE (T18)**: resposta final em eventos (`resposta` + `fim`), não token a
  token; rota `GET`; **401** (API), não redirect.
- **Chat UI (T19)**: página (`GET /chat`, 303 sem sessão) separada do fragmento
  (`GET /chat/pergunta`); resposta como `textContent` (anti-XSS) e
  `sse-close="fim"` (não reexecuta o grafo).
- **Histórico (T20)**: histórico é **exibição**, nunca realimentado no grafo
  (evita prompt injection persistente); débitos na ADR: `get_or_create` não
  atômico (falta `UniqueConstraint(empresa_id, user_id)`), limite
  `String(4000)` por mensagem, ordenação por `created_at, id`.
- **Recomendação (T21)**: a resposta só é uma recomendação se vier da **tool
  comum**; sem fonte citável vira `MENSAGEM_INSUFICIENCIA` (não persiste
  `Recommendation`). O parser lê o formato próprio escrito pela tool (rótulos
  compartilhados); `answer()` devolve o texto composto cru (com rótulos) no
  caminho feliz — a apresentação limpa é a T23. Débitos: distinguir "sem base" de
  "preciso de um dado do usuário" (COP-02 AC3) e formatar a exibição.
- **Fluxo da task**: cortar `feat/f1-tXX-*` de `feat/f1-mvp` → implementar
  (`build-with-tests`) → **self-review obrigatório** (`developer-self-reviewer` +
  ADR fluid-hybrid) logo após o build, **antes do gate** → gate (`pytest` +
  `black` + `ruff`) → commit PT `feat(f1): ...` → PR contra `feat/f1-mvp` →
  **code review** (`code-reviewer`) → squash + apagar branch. *(Ordem conforme
  `feature-factory` Phase 5.5: o self-review é a fase 5.5, imediatamente após o
  builder; o code review é sobre o PR já aberto.)*
- **Ambiente Windows**: o App Control bloqueia os `.exe` do `.venv` e a DLL
  `_uuid_utils` (plugin `langsmith`). Rodar com `uv run python -m black|ruff` e
  `uv run python -m pytest -p no:langsmith`.

## Próximos passos / bloqueios

1. **T22 — PENDENTE** (próxima ação): **Feedback aceitar/descartar** — endpoint
   que registra `Feedback` (decisão, usuário, empresa, timestamp). Where
   `src/gestlog/web/`, `src/gestlog/repositories/`; depends T21; reuses T5.
   Requirement COP-06; **testes integration**. A T21 já persiste a
   `Recommendation`, então o `Feedback` pode apontar para o id real. Branch
   `feat/f1-t22-*` → PR contra `feat/f1-mvp`.
2. T23–T33 seguem (UI de feedback, PII/auditoria/uso, custo/eval, admin…).
3. Ao fechar a F1: PR de release `feat/f1-mvp → main` + tag `v0.1.0`.
4. Pendência técnica (pós-T17): os `TOOLS` mock ainda são fallback do REPL; DB no
   CLI/remoção do mock quando não houver mais uso.
5. Débitos da T20 (registrados na ADR `t20-historico-conversa-self-review.md`):
   `UniqueConstraint(empresa_id, user_id)` em `conversation`; reavaliar
   `String(4000)`/migrar para `Text`; mover `get_sync_session` de
   `ingestion_ui.py` para um `web/deps.py`.
6. Opcional: remover backups locais `backup/f1-fase2` e `backup/f1-mvp` (sem uso).
7. Opcional: avaliar o plugin `@opencode-ai/plugin` em `.opencode/`.

## WIP local (não commitado)

- **Este handoff** (atualização de T21) ainda não commitado na `feat/f1-mvp`; o
  restante da árvore está limpo. `HEAD` de `feat/f1-mvp` = `88f5b38` (sincronizado
  com `origin/feat/f1-mvp`).

## Artefatos do graphify

- **graphify indisponível para o gestlog.** `graphify_graph_stats`,
  `graphify_god_nodes` e `graphify_query_graph` retornaram
  `graph.json not found: C:\Users\ander\8_projetos\gestlog\graphify-out\graph.json`
  (`Test-Path graphify-out/graph.json` = `False`). O `opencode.json` aponta o MCP
  para `C:\Users\ander\8_projetos\medasist\graphify-out\graph.json` (OUTRO
  repositório) — **não representa o gestlog**. **Nenhum número registrado (não
  verificado); não inventar valores.**
- Módulos tocados nesta sessão: `src/gestlog/auth/`, `src/gestlog/copilot/`,
  `src/gestlog/repositories/conversations.py`, `src/gestlog/web/` e `docs/adr/`.
  Comunidades afetadas: **não verificado** (sem grafo do gestlog).

## Documentos de projeto relevantes

- `AGENTS.md` — arquitetura, convenções, comandos e fluxo épico+task.
- `README.md`, `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`.
- `docs/business/PRD.md`.
- `docs/specs/project/{PROJECT,ROADMAP,STATE}.md` — TLC; decisões AD-001..AD-016.
- `docs/specs/features/f1-mvp/{spec,design,tasks}.md` — planejamento da F1
  (`tasks.md`: 34 tasks; T1–T21 e T34 concluídos).
- `docs/specs/codebase/TESTING.md` — matriz de testes e gates.
- `docs/adr/` — self-reviews **fluid-hybrid**: `t13-upload-ui`, `t14-inventory-tools`,
  `t15-supplier-tools`, `t16-transport-tools`, `t34-common-response`,
  `t17-copilot-service`, `t18-chat-sse`, `t19-chat-ui`,
  `t20-historico-conversa-self-review`,
  `t21-recomendacao-fontes-insuficiencia-self-review` (todos sufixo `-self-review`).
- `src/gestlog/`: `config.py`, `llm.py`, `graph.py`, `state.py`, `cli.py`,
  `agents/` (`base.py` detecta a tool comum terminal; `dominio` no estado),
  `tools/` (`common.py` = tool comum + rótulos), `db/`, `repositories/`, `auth/`,
  `web/` (`chat.py` = SSE T18; `chat_ui.py` = UI T19/T20; `templates/chat*.html`),
  `copilot/` (`service.py` = `Recomendacao`/`extrair_recomendacao`/persistência),
  `ingestion/`.
- `.opencode/skills/` — build-with-tests, code-reviewer, feature-factory,
  git-workflow, ship-feature, write-fluid-hybrid-adr.
- `.opencode/agent/` — backend-builder, codebase-researcher,
  developer-self-reviewer, frontend-builder, persistence-checker, spec-writer,
  story-writer, test-verifier, validator.
- `.opencode/command/` — start, end, explain, run-tests.

---

# Histórico (sessões anteriores, resumido)

- **2026-09-17 (esta):** handoff validado/corrigido (`c016131`); **T20 concluída e
  mergeada** (PR #21, squash `0ab9e03` — persistência/histórico por usuário e
  empresa, ADR `t20-historico-conversa-self-review`); correção da ordem do fluxo
  (`87cc0ab`); **T21 concluída e mergeada** (PR #22, squash `88f5b38` —
  recomendação + justificativa + fontes e insuficiência, tool comum como passo
  terminal, ADR `t21-recomendacao-fontes-insuficiencia-self-review`); 139→147
  testes (97,58%→97,68%). F1 retoma na **T22**.
- **2026-09-16:** skill `write-fluid-hybrid-adr` criada; **T19 mergeada** (PR #20,
  `450df94` — UI do chat HTMX/SSE); ADRs t13–t18/t34 refeitas no formato
  fluid-hybrid (`cf0924f`).
- **2026-09-15:** T15 (`a5fbcfe`), T16 (`2387a0e`), T34 (`ebf185e`), T17
  (`6599c5c`), T18 (`61172a5`) concluídas e mergeadas; 109→125 testes.
- **2026-09-15 (anterior):** T14 concluído e mergeado (PR #14, `12c046f`) — tools
  de estoque por tenant.
- **2026-09-14:** T13 (PR #13, `fcd93fc`) e T12 (PR #12, `224f918`); fase 5.5 de
  self-review/ADR adicionada ao pipeline (`2443b92`).
- **2026-09-13:** code review dos PRs stacked (AD-014/015); fluxo épico + 1 PR/task
  com CI (AD-016); T10 (PR #6) e T11 (PR #8).
- **2026-09-12:** catálogo de tools (AD-010); docs-as-code (AD-011); fronteiras do
  pacote (AD-012); auth async (AD-013); T6–T9.
- **2026-09-11:** scaffold `.opencode/`; PRD + TLC; F1 planejada; rename
  `Tenant`→`Empresa`.
