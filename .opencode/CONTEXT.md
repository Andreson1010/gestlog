# Contexto da Sessão — F1 entregue: release v0.1.0 na main

> Handoff persistente. `/end` grava, `/start` lê. Última atualização: 2026-09-18.
> Branch: `main` · HEAD: `1c0768c` (squash do release PR #35) · tag `v0.1.0`.
> A integração `feat/f1-mvp` foi promovida e **apagada**; `main` é a verdade agora.

## Estado atual

- **gestlog**: fluxo multiagente em LangGraph (supervisor + especialistas
  transporte / fornecedores / estoque) com tools `@tool`. Remote `origin` =
  https://github.com/Andreson1010/gestlog (privado).
- **F1 (MVP) ENTREGUE E RELEASADA**: **34/34 tasks**; `main` = `1c0768c`, tag
  `v0.1.0` (release PR #35). O épico inteiro está em `main`.
- Stack travado (AD-007): FastAPI + Jinja2/HTMX/SSE + Postgres (`empresa_id`) +
  FastAPI Users. Modelo de entrega (AD-016): `main` verde, `1 PR por task` com CI +
  self-review + `code-reviewer`; release único `feat/f1-mvp → main` + tag `v0.1.0`.
- **CI**: `.github/workflows/ci.yml` — `black --check`, `ruff check`, `pytest`
  (gate 80%) em PRs e push. Release PR #35 e o push em `main` verdes.
- **Suíte**: **248 testes, 98,26% de cobertura** (`uv run pytest`, re-verificado na
  T33); Python 3.14.3 no `.venv` (projeto exige `>=3.11`). `privacy/`, `audit/`,
  `metering.py`, `state.py`, `agents/base.py`, `evaluation/golden.py` com **100%**.
- `main` = `1c0768c` (= `origin/main`, **em sincronia**). **Árvore limpa; nenhum
  stash; nenhum PR aberto; nenhuma branch de task** (refs remotas podadas).
- **Última entrega — release `v0.1.0`** (ver *O que foi feito*): PR #35 promoveu a
  F1 para `main` e a tag/release `v0.1.0` foi publicada.

## O que foi feito nesta sessão (2026-09-17/18)

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
4. **T24 — Módulo de redação de PII** (PR #25, squash `eff38a4`). Novo pacote
   `src/gestlog/privacy/`: `redact(texto, politica) -> RedactedText` (frozen) com
   regex + allowlist, **sem LLM**; telefones/endereços/CEP/nomes →
   `[TELEFONE]`/`[ENDERECO]`/`[NOME]`; nomes casam forma acentuada e forma sem
   diacríticos (NFKD); marcador literais via escape de `\` no `re.sub`. Self-review
   achou e corrigiu nome sem acentuação não redigido (SEC-01 real), marcador com
   `\` estourando `re.sub` e ordenação não determinística. ADR
   `t24-...-self-review.md`; `privacy/` 100% coberto. Integração fica na T25.
5. **T25 — Integrar redação no copiloto** (PR #26, squash `555c992`).
   `CopilotService.answer` aplica `redact(pergunta)` antes de `run_query` e grava a
   **versão redigida** em `Message.conteudo_redigido`; o original não vai ao LLM nem
   é persistido (decisão do usuário, alinhada à ADR da T20). `FakeChatModel` ganhou
   `mensagens_recebidas` para o teste do *Done when* inspecionar o prompt real.
   ADR `t25-...-self-review.md`.
6. **T26 — Auditoria e retenção** (PR #27, squash `ad13821`). Novo pacote
   `src/gestlog/audit/`: catálogo de eventos validado + `registrar_evento` (sem
   commit, entra na unidade de trabalho) e `purgar_expiradas` (prazo por empresa,
   fallback ao default; SQL no repositório, ordem de FK). `CopilotService.answer`
   registra `pergunta` (detalhe com domínio + categorias de PII, sem o valor) e
   `recomendacao` (domínio + fontes). Self-review adicionou guarda de `datetime`
   naive. ADR `t26-...-self-review.md`.
7. **T27 — Medição de uso e quota** (PR #28, squash `1fc5419`).
   `src/gestlog/copilot/metering.py`: `record_usage` (tokens/modelo por empresa,
   sem commit) e `check_quota` (soma do **mês corrente** via
   `UsageRepository.total_tokens_desde`, levanta `QuotaExcedida` tipada ao atingir
   `Settings.llm_monthly_token_quota`). Integração no copiloto fica na T28. ADR
   `t27-...-self-review.md`.
8. **T28 — Medição por chamada + bloqueio de quota** (PR #29, squash `50289d1`).
   `AgentState.tokens_usados` (reducer `operator.add`) acumula `usage_metadata` no
   nó especialista (as mensagens intermediárias são descartadas, então a soma vive
   no estado). `answer` checa a quota antes de chamar o LLM; ao estourar devolve
   `MENSAGEM_QUOTA_EXCEDIDA` sem invocar o modelo nem persistir turno. Uso gravado
   junto do turno. Tokens do supervisor ficam fora da soma. ADR
   `t28-...-self-review.md`.
9. **T29 — Golden set (formato + runner)** (PR #30, squash `bd2decd`).
   `src/gestlog/evaluation/golden.py`: `CasoGolden` + `carregar_golden_set` (JSON
   validado) + `run_golden_set` (grafo real, modelo injetado) reusando
   `extrair_recomendacao`; `RelatorioAvaliacao` com acurácia/alucinação/fonte.
   `evals/golden_set.json` é o dataset-semente. `copilot.service.texto_resposta`
   virou público. Script real é a T30. ADR `t29-...-self-review.md`.
10. **T30 — Script de avaliação** (PR #31, squash `bb1e8c5`).
    `evaluation/script.py` (`gerar_relatorio` com modelo injetável,
    `salvar_relatorio`, `main`) + `evaluation/relatorio.py` (acurácia por domínio,
    JSON) e launcher `evals/run_golden_set.py`; relatório em
    `evals/relatorio.json` (ignorado no git). ADR `t30-...-self-review.md`.
11. **T31 — Gestão de usuários e papéis** (PR #32, squash `1685a76`).
    `web/admin.py` (`GET/PATCH/DELETE /empresa/usuarios`) sob `exigir_papel("admin")`
    + casos de uso em `auth/accounts.py` (último admin protegido, 404 entre
    empresas). Contornado defeito latente `Membership.user_id` (`Uuid`) ×
    `User.id` (`GUID`) no JOIN do SQLite. ADR `t31-...-self-review.md`.
12. **T32 — Dashboard de KPIs** (PR #33, squash `94213b9`).
    `repositories/kpis.py` (`KpiRepository.resumo` com adoção/aceitação/cobertura;
    decisão vigente "última vence") + `GET /kpis` (admin/gestor) e `kpis.html`.
    Período por data (UTC inclusivo); cobertura é snapshot. ADR
    `t32-...-self-review.md`.
13. **T33 — Testes de aceitação P1** (PR #34, squash `564bcbd`). Arquivo único
    `tests/acceptance/test_f1_mvp.py` cobrindo ACC-01..04, ING-01..03, COP-01..06,
    SEC-01..03 e QUA-01..02 (HTTP real onde há endpoint; SEC-02/QUA-01 chamam o
    serviço direto), com fake model e banco em `tmp_path`. Fecha a F1. ADR
    `t33-...-self-review.md`.
14. **Release v0.1.0** (PR #35, squash `1c0768c`). PR único `feat/f1-mvp → main`
    promoveu a F1 completa; tag anotada `v0.1.0` publicada e GitHub Release criado
    (`gh release create`); CI do push em `main` verde; integração apagada.
15. **Docs**: `STATE.md` com **AD-017** a **AD-029**; `tasks.md` com progresso até
    T33 (F1 completa); handoffs `c016131`/`87cc0ab`/`19e72c5`/`43f0bd9`/`bfef8d3`/
    `d30fed3`, correção de HEAD `e05e77b`, `8b06f41` e `60da514`.
16. **Fluxo**: todas as tasks seguiram build → **self-review (ADR)** → gate
    (`pytest`+`black`+`ruff`) → commit PT → PR → **code review** → squash. Code
    review: **0 CRITICAL/HIGH** nas treze tasks.

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
- **PII (T24)**: `privacy/` determinístico, regex + allowlist, **sem LLM**;
  over-redação é o erro seguro; nomes sem acento também redigidos.
- **PII (T25)**: pergunta redigida vai ao LLM **e** é a persistida no histórico
  (`conteudo_redigido`); original não circula nem é retido; UI ao vivo mostra o
  original. Política por tenant ainda não existe (usa `POLITICA_PADRAO`).
- **Auditoria/retenção (T26)**: catálogo de eventos validado; `registrar_evento`
  sem commit (entra na unidade de trabalho do turno); `detalhe` só metadados, nunca
  PII; retenção por empresa com fallback ao default; SQL de purga só em
  `repositories/` (ordem de FK). `UsageRecord`/`AuditLog` não são purgados.
- **Uso/quota (T27)**: quota **mensal** por empresa (`Settings.llm_monthly_token_quota`),
  `check_quota` é pré-chamada (best-effort) e levanta `QuotaExcedida` (>= quota);
  `record_usage` sem commit; `total_tokens` (all-time) segue para KPIs.
- **Uso/quota (T28)**: `AgentState.tokens_usados` (reducer soma) acumula uso no nó
  especialista; `answer` checa quota antes do LLM e devolve `MENSAGEM_QUOTA_EXCEDIDA`
  sem persistir; uso gravado na mesma transação do turno. Tokens do supervisor não
  somam.
- **Golden set (T29)**: formato JSON (`evals/golden_set.json`) + runner
  `run_golden_set` reusando `extrair_recomendacao`; métricas acurácia/alucinação/
  fonte; fake model nos testes; `texto_resposta` público. Script real é a T30.
- **Avaliação/script (T30)**: lógica testável em `evaluation/script.py`
  (modelo injetável; default real), launcher fino em `evals/run_golden_set.py`;
  `evals/relatorio.json` é artefato gerado (ignorado). Operação manual, não agendada.
- **Admin/papéis (T31)**: rotas `/empresa/usuarios` sob `exigir_papel("admin")`;
  404 entre empresas; último admin protegido (409); remoção apaga o vínculo e
  revoga acesso. Débito: `Membership.user_id` (`Uuid`) × `User.id` (`GUID`) não
  fazem JOIN no SQLite (contornado com `IN`).
- **KPIs (T32)**: `KpiRepository.resumo(empresa_id, desde, ate)` agrega adoção/
  aceitação/cobertura; aceitação = decisão vigente (última vence, T22); cobertura
  é snapshot (dados sem `created_at`); `GET /kpis` exige admin/gestor; período por
  data em UTC inclusivo. Empates de timestamp desempatam por UUID (limitação T20/T23).
- **Aceitação (T33)**: arquivo único cobrindo os IDs P1 por nome de teste; fake
  model + banco em `tmp_path`; HTTP real onde há endpoint, serviço direto em
  SEC-02/QUA-01. Fecha a F1.
- **Fluxo da task (F1, concluído)**: `feat/f1-tXX-*` de `feat/f1-mvp` →
  build-with-tests → **self-review (ADR)** → gate → commit PT → PR → **code
  review** → squash. Release final `feat/f1-mvp → main` + tag `v0.1.0` (feito).

## Próximos passos / bloqueios

1. **F1 entregue (v0.1.0)** — nada pendente do épico. Próximo épico: **F2**
   (tools de escrita/ação com HITL — AD-001).
2. **Débito T23**: turno ao vivo (SSE) ainda não recebe botões — a decisão só
   aparece ao recarregar o histórico; emitir `event: fontes`/fragmento e ordenação
   monotônica de mensagens (substituir pareamento por `created_at`) fica futuro.
3. **Débitos T20/T31**: `UniqueConstraint(empresa_id, user_id)`; reavaliar
   `String(4000)`/`Text`; mover `get_sync_session` de `ingestion_ui.py` para
   `web/deps.py`; alinhar `Membership.user_id` (`Uuid`) a `User.id` (`GUID`) para
   permitir JOIN (migration).
4. **Pendência pós-T17**: remover `TOOLS` mock do REPL quando a CLI ganhar banco.
5. **Auditoria faltante**: feedback e importação ainda não registram em `AuditLog`
   (só pergunta/recomendação no copiloto).
6. Opcional: remover backups locais `backup/f1-fase2`/`backup/f1-mvp`; avaliar o
   plugin `@opencode-ai/plugin` em `.opencode/`.

## WIP local (não commitado)

- **Nenhum.** Árvore limpa. `main` sincronizada com `origin/main` em `1c0768c`
  (release `v0.1.0`); sem stash e sem PR aberto.

## Artefatos do graphify

- **graphify indisponível para o gestlog.** `graphify_graph_stats` retornou
  `graph.json not found: C:\Users\ander\8_projetos\gestlog\graphify-out\graph.json`
  (`Test-Path graphify-out/graph.json` = `False`). O `opencode.json` aponta o MCP
  para `C:\Users\ander\8_projetos\medasist\graphify-out\graph.json` (OUTRO repo) —
  **não representa o gestlog**. **Nenhum número registrado (não verificado); não
  inventar valores.**
- Módulos tocados nesta sessão: `src/gestlog/{copilot,privacy,audit,evaluation,agents,tools,repositories,auth,web}/`
  e `state.py`; `evals/`; docs em `docs/adr/` e `docs/specs/`. Comunidades afetadas:
  **não verificado** (sem grafo do gestlog).

## Documentos de projeto relevantes

- `AGENTS.md` — arquitetura, convenções, comandos e fluxo épico+task.
- `README.md`, `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`.
- `docs/business/PRD.md`.
- `docs/specs/project/{PROJECT,ROADMAP,STATE}.md` — TLC; decisões AD-001..AD-029.
- `docs/specs/features/f1-mvp/{spec,design,tasks}.md` — F1 (`tasks.md`: 34/34 concluídos).
- `docs/specs/codebase/TESTING.md` — matriz de testes e gates.
- `docs/adr/` — self-reviews **fluid-hybrid** (sufixo `-self-review`): `t13` a
  `t33` + `t34` (22 arquivos).
- `src/gestlog/`: `config.py`, `llm.py`, `graph.py`, `state.py`, `cli.py`,
  `agents/` (base detecta tool comum terminal; `dominio`; acumula `tokens_usados`), `tools/`
  (`common.py` = tool comum + rótulos), `db/`, `repositories/`
  (`conversations.py` = conversas/mensagens/recomendações/feedback; `kpis.py` =
  agregações), `auth/`
  (`accounts.py` = conta/convite + gestão de usuários), `web/` (`chat.py` SSE;
  `chat_ui.py` UI; `feedback.py` T22/T23; `admin.py` = usuários/papéis; `kpis.py` =
  dashboard; `templates/`),
  `copilot/` (`service.py` = `Recomendacao`/`extrair_recomendacao`/`Turno`; `answer`
  redige a PII antes do LLM e audita; `metering.py` = `record_usage`/`check_quota`),
  `privacy/` (`politica.py` = allowlist/marcadores; `redacao.py` = `redact`),
  `audit/` (`eventos.py` = catálogo + `registrar_evento`; `retencao.py` =
  `purgar_expiradas`), `evaluation/` (`golden.py` = formato + runner;
  `script.py`/`relatorio.py` = CLI + relatório), `ingestion/`. Também `evals/`
  (`golden_set.json`, `run_golden_set.py`) e `tests/acceptance/test_f1_mvp.py`.
- `.opencode/skills/` — build-with-tests, code-reviewer, feature-factory,
  git-workflow, ship-feature, write-fluid-hybrid-adr.
- `.opencode/agent/` — backend-builder, codebase-researcher,
  developer-self-reviewer, frontend-builder, persistence-checker, spec-writer,
  story-writer, test-verifier, validator.
- `.opencode/command/` — start, end, explain, run-tests.

---

# Histórico (sessões anteriores, resumido)

- **2026-09-18 (esta):** **T24** (PR #25, `eff38a4` — redação de PII, AD-020),
  **T25** (PR #26, `555c992` — integração no copiloto, AD-021), **T26** (PR #27,
  `ad13821` — auditoria + retenção, AD-022), **T27** (PR #28, `1fc5419` — uso/quota,
  AD-023), **T28** (PR #29, `50289d1` — medição + bloqueio, AD-024), **T29**
  (PR #30, `bd2decd` — golden set, AD-025), **T30** (PR #31, `bb1e8c5` — script de
  avaliação, AD-026), **T31** (PR #32, `1685a76` — gestão de usuários/papéis,
  AD-027), **T32** (PR #33, `94213b9` — dashboard de KPIs, AD-028) e **T33**
  (PR #34, `564bcbd` — aceitação P1, AD-029) concluídas e mergeadas; 157→248 testes
  (97,76%→98,26%). **F1 completa e releasada: PR #35 (`1c0768c`) na `main` + tag
  `v0.1.0`.**
- **2026-09-17:** **T21** (PR #22, `88f5b38`), **T22** (PR #23, `0dfc1dc`) e
  **T23** (PR #24, `5bcac81`) concluídas e mergeadas; `STATE.md` ganhou AD-017/018/019;
  139→157 testes (97,58%→97,76%).
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
