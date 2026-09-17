# F1 — MVP do gestlog — Tasks

**Design**: `docs/specs/features/f1-mvp/design.md`
**Status**: In progress
**Progresso**: T1–T5 ✅ · T6 ✅ · T7 ✅ · T8 ✅ · T9 ✅ · T10 ✅ · T11 ✅ · T12 ✅ · T13 ✅ · T14 ✅ · T15 ✅ · T16 ✅ · T17 ✅ · T18 ✅ · T34 ✅ · T19 ✅ · T20 ✅ · T21 ✅ · T22 ✅ · T23 ✅ · T24–T33 pendentes

---

## Execution Plan

### Phase 0 — Setup (sequential)

```
T1 → T2
```

### Phase 1 — Persistência (sequential)

```
T2 → T3 → T4
        └→ T5
```

### Phase 2 — Auth & Tenancy (sequential)

```
T4 → T6 → T7 → T8
```

### Phase 3 — Web shell (sequential)

```
T7 → T9 → T10
```

### Phase 4 — Ingestão

```
T2 ─┬→ T11 ─┐
    └───────┴→ T12 → T13
T5 ──────────┘
T10 ──────────────→ T13
```

### Phase 5 — Tools do tenant (parallel)

```
T5 ─┬→ T14 [P]
    ├→ T15 [P]
    ├→ T16 [P]
    └→ T34 [P]
```

### Phase 6 — Copiloto

```
T14,T15,T16,T34 → T17 → T18 ─┬→ T19
                             └→ T20
T7 ──────────────────────┘
T10 ─────────────────────→ T19
```

### Phase 7 — Recomendação

```
T17 → T21 → T22 → T23
T19 ─────────────┘
```

### Phase 8 — Privacidade & Auditoria

```
T1 → T24 [P] ─┐
              └→ T25
T17 ──────────┘
T5,T17 → T26
```

### Phase 9 — Custo

```
T5 → T27 → T28
T17 ──────┘
```

### Phase 10 — Qualidade

```
T17 → T29 → T30
```

### Phase 11 — Admin & Dashboard

```
T8 → T31
T5 → T32
```

### Phase 12 — E2E Acceptance

```
(P1 concluído) → T33
```

---

## Task Breakdown

### T1: Adicionar dependências da F1

**What**: Adicionar FastAPI, uvicorn, jinja2, python-multipart, sqlalchemy,
alembic, psycopg, fastapi-users, pwdlib[argon2], pandas/openpyxl ao
`pyproject.toml` e sincronizar.
**Where**: `pyproject.toml`, `requirements*.txt` (espelho)
**Depends on**: None · **Reuses**: `pyproject.toml` · **Requirement**: infra
**Tests**: none · **Gate**: build
**Done when**: `uv sync --extra dev` instala; `uv run pytest` continua verde.

### T2: Estender `Settings` (DB, auth, retenção, quotas) [P]

**What**: Novos campos de config (URL do DB, segredo de auth, retenção padrão,
quota de LLM) com validação.
**Where**: `src/gestlog/config.py` (modify) · **Depends on**: T1 · **Reuses**: `Settings`, `get_settings`
**Requirement**: QUA-02, SEC-02 · **Tests**: unit · **Gate**: quick
**Done when**: campos validados; testes cobrindo defaults/limites; gate passa.

### T3: Base/sessão SQLAlchemy + modelos

**What**: `Base`, engine/session factory e os modelos do design (Tenant, Membership,
ImportJob/Error, StockItem, Supplier, TransportRecord, Conversation, Message,
Recommendation, Feedback, UsageRecord, AuditLog).
**Where**: `src/gestlog/db/` · **Depends on**: T2 · **Reuses**: —
**Requirement**: ACC-01, ACC-04 · **Tests**: integration · **Gate**: quick
**Done when**: modelos criam schema em SQLite de teste; `tenant_id` em todas as tabelas de dados.

### T4: Alembic + migration inicial

**What**: Configurar Alembic e gerar a migration que cria todas as tabelas.
**Where**: `alembic/`, `alembic.ini` · **Depends on**: T3 · **Reuses**: modelos T3
**Requirement**: ACC-01 · **Tests**: integration · **Gate**: quick
**Done when**: `alembic upgrade head` sobe o schema; teste de migration passa.

### T5: Repositórios com escopo de tenant

**What**: Repositórios que sempre filtram por `tenant_id` (tenant, membros,
import, estoque, fornecedor, transporte, conversa, uso, auditoria).
**Where**: `src/gestlog/repositories/` · **Depends on**: T3 · **Reuses**: T3
**Requirement**: ACC-04 · **Tests**: integration · **Gate**: quick
**Done when**: nenhuma query sem filtro de tenant; teste de isolamento entre 2 tenants passa.

### T6: FastAPI Users (login/logout)

**What**: Modelo de usuário, backend de auth e rotas de login/logout por cookie.
**Where**: `src/gestlog/auth/`, `src/gestlog/web/` · **Depends on**: T4 · **Reuses**: `Settings`
**Requirement**: ACC-02 · **Tests**: integration · **Gate**: quick
**Done when**: login/logout funcionam; senha com hash; teste de credencial inválida.

### T7: Membership, resolução de tenant e guards

**What**: Ligar usuário a tenant/papel e expor dependências `get_current_tenant`
e guardas de acesso; negar acesso cruzado com 404.
**Where**: `src/gestlog/auth/` · **Depends on**: T6 · **Reuses**: T5, T6
**Requirement**: ACC-03, ACC-04 · **Tests**: integration · **Gate**: quick
**Done when**: teste cria 2 tenants e confirma que nenhum recurso cruza; 401 sem sessão.

### T8: Onboarding da conta, convites e papéis

**What**: Fluxo de criação de conta (tenant) e convite de usuários com papel
(admin/operador/gestor).
**Where**: `src/gestlog/web/`, `src/gestlog/auth/` · **Depends on**: T7 · **Reuses**: T7
**Requirement**: ACC-01, ACC-03, ADM-01 · **Tests**: integration · **Gate**: quick
**Done when**: criar conta → convidar → usuário acessa restrito ao tenant; teste passa.

### T9: App factory + layout Jinja/HTMX

**What**: Factory da aplicação FastAPI, templates base, estáticos e HTMX.
**Where**: `src/gestlog/web/` · **Depends on**: T7 · **Reuses**: —
**Requirement**: infra · **Tests**: integration · **Gate**: quick
**Done when**: app sobe em teste; página base renderiza; assets servidos.

### T10: Home autenticada e navegação

**What**: Página inicial autenticada com navegação para Importar e Chat.
**Where**: `src/gestlog/web/` · **Depends on**: T9 · **Reuses**: T9
**Requirement**: infra · **Tests**: integration · **Gate**: quick
**Done when**: rota autenticada renderiza; não autenticado redireciona ao login.

### T11: Parsers e validadores de importação [P]

**What**: Leitura e validação/normalização de CSV/planilha por tipo (estoque,
fornecedores, transporte), com erros por linha.
**Where**: `src/gestlog/ingestion/` · **Depends on**: T2 · **Reuses**: padrões do repo
**Requirement**: ING-01, ING-02 · **Tests**: unit · **Gate**: quick
**Done when**: arquivo válido → registros normalizados; linhas inválidas → motivos; testes de vazio/tipo desconhecido.

### T12: Serviço de importação e status

**What**: Persistir `ImportJob`/`ImportError`, aplicar upsert e expor status.
**Where**: `src/gestlog/ingestion/`, `src/gestlog/repositories/` · **Depends on**: T5, T11 · **Reuses**: T5, T11
**Requirement**: ING-02, ING-03 · **Tests**: integration · **Gate**: quick
**Done when**: import grava aceitas/rejeitadas e histórico por tenant; teste passa.

### T13: UI de upload e status

**What**: Tela HTMX de upload e de status/histórico de importação.
**Where**: `src/gestlog/web/` · **Depends on**: T10, T12 · **Reuses**: T10, T12
**Requirement**: ING-01, ING-03 · **Tests**: integration · **Gate**: quick
**Done when**: upload reflete status com contagens; erros por linha visíveis.

### T14: Tools de estoque por tenant [P]

**What**: `consultar_estoque`/`calcular_reposicao`/`listar_movimentacoes` lendo do
repositório do tenant (mesmas assinaturas) + novas tools de análise
`prever_demanda`/`otimizar_armazem`/`otimizar_custos` (ver catálogo no design.md).
**Where**: `src/gestlog/tools/inventory.py` (modify) · **Depends on**: T5 · **Reuses**: assinaturas atuais
**Requirement**: COP-02 · **Tests**: unit (fake repo) · **Gate**: quick
**Done when**: tools retornam dados do tenant; SKU ausente tratado; novas tools read-only; testes passam.

### T15: Tools de fornecedores por tenant [P]

**What**: Tools de fornecedores lendo do repositório do tenant + nova
`tratar_conformidade` (checagem read-only na F1).
**Where**: `src/gestlog/tools/suppliers.py` (modify) · **Depends on**: T5 · **Reuses**: assinaturas atuais
**Requirement**: COP-02 · **Tests**: unit (fake repo) · **Gate**: quick
**Done when**: tools retornam dados do tenant; ausência tratada; testes passam.

### T16: Tools de transporte por tenant [P]

**What**: Tools de frete/prazo/rastreio com dados do tenant (mantendo cálculo) +
nova `otimizar_entrega` (read-only).
**Where**: `src/gestlog/tools/transport.py` (modify) · **Depends on**: T5 · **Reuses**: assinaturas atuais
**Requirement**: COP-02 · **Tests**: unit (fake repo) · **Gate**: quick
**Done when**: tools retornam dados do tenant; testes passam.

### T34: Tool comum `enviar_resposta_logistica` [P]

**What**: Tool read-only compartilhada pelos três especialistas que compõe a
resposta logística (sem envio externo na F1); fonte única em `tools/common.py`.
**Where**: `src/gestlog/tools/common.py` (new), `src/gestlog/tools/__init__.py` (modify) · **Depends on**: T5
**Reuses**: padrões de `@tool` atuais · **Requirement**: COP-02 · **Tests**: unit (fake repo) · **Gate**: quick
**Done when**: os três especialistas expõem a tool; teste confirma composição da resposta.

### T17: Copilot Service (grafo + contexto do tenant)

**What**: Serviço que injeta o `tenant_id` no contexto das tools, roda o grafo e
devolve a resposta; modelo injetável para teste.
**Where**: `src/gestlog/copilot/` · **Depends on**: T14, T15, T16 · **Reuses**: `graph.build_graph`, `state.AgentState`, `conftest.fake_model_cls`
**Requirement**: COP-01, COP-02 · **Tests**: unit (fake model) · **Gate**: quick
**Done when**: pergunta de cada domínio roteia e responde com fake model; fora de escopo tratado.

### T18: Endpoint de chat com SSE

**What**: Rota autenticada que recebe a pergunta e transmite a resposta (SSE).
**Where**: `src/gestlog/web/` · **Depends on**: T17, T7 · **Reuses**: T17
**Requirement**: COP-01, COP-05 · **Tests**: integration · **Gate**: quick
**Done when**: SSE emite a resposta; sem sessão → 401; teste passa.

### T19: UI do chat (HTMX/SSE)

**What**: Tela de chat consumindo o endpoint SSE.
**Where**: `src/gestlog/web/` · **Depends on**: T10, T18 · **Reuses**: T10, T18
**Requirement**: COP-01, COP-05 · **Tests**: integration · **Gate**: quick
**Done when**: pergunta e resposta aparecem via streaming na tela.

### T20: Persistência e histórico da conversa

**What**: Gravar conversa/mensagens por usuário/tenant e exibir histórico ao voltar.
**Where**: `src/gestlog/copilot/`, `src/gestlog/web/` · **Depends on**: T18 · **Reuses**: T5
**Requirement**: COP-06 · **Tests**: integration · **Gate**: quick
**Done when**: recarregar mantém o histórico no tenant correto.

### T21: Extração de recomendação, fontes e insuficiência

**What**: Estruturar a resposta como recomendações com justificativa e fontes;
detectar dado insuficiente.
**Where**: `src/gestlog/copilot/` · **Depends on**: T17 · **Reuses**: T17
**Requirement**: COP-03, COP-04 · **Tests**: unit (fake model) · **Gate**: quick
**Done when**: resposta traz fontes; caso sem base retorna insuficiência sem alucinar.

### T22: Feedback aceitar/descartar

**What**: Endpoint que registra `Feedback` (decisão, usuário, tenant, timestamp).
**Where**: `src/gestlog/web/`, `src/gestlog/repositories/` · **Depends on**: T21 · **Reuses**: T5
**Requirement**: COP-06 · **Tests**: integration · **Gate**: quick
**Done when**: aceite/descarte persistido por tenant; teste passa.

### T23: UI de feedback

**What**: Botões aceitar/descartar e exibição de fontes na tela de chat.
**Where**: `src/gestlog/web/` · **Depends on**: T19, T22 · **Reuses**: T19, T22
**Requirement**: COP-04, COP-06 · **Tests**: integration · **Gate**: quick
**Done when**: aceite/descarte refletem sem recarregar (HTMX).

### T24: Módulo de redação de PII [P]

**What**: `redact(text)` que remove/minimiza nomes, endereços e telefones antes do LLM.
**Where**: `src/gestlog/privacy/` · **Depends on**: T1 · **Reuses**: —
**Requirement**: SEC-01 · **Tests**: unit · **Gate**: quick
**Done when**: casos de nome/endereço/telefone redigidos; texto sem PII intacto.

### T25: Integrar redação no copiloto

**What**: Redigir PII do texto do usuário antes de enviar ao LLM, preservando o
texto original para a UI.
**Where**: `src/gestlog/copilot/` · **Depends on**: T17, T24 · **Reuses**: T24
**Requirement**: SEC-01, SEC-03 · **Tests**: unit · **Gate**: quick
**Done when**: teste confirma que o prompt ao LLM não contém a PII de entrada.

### T26: Auditoria e retenção

**What**: Serviço de `AuditLog` por tenant e política de retenção configurável
(purga de conversas/dados além do período).
**Where**: `src/gestlog/audit/`, `src/gestlog/repositories/` · **Depends on**: T5, T17 · **Reuses**: T5
**Requirement**: SEC-02, SEC-03 · **Tests**: integration · **Gate**: quick
**Done when**: eventos registrados; retenção expira o que passou do prazo.

### T27: Medição de uso e quota

**What**: Registrar tokens/modelo por tenant e checar quota antes da chamada.
**Where**: `src/gestlog/copilot/metering.py` · **Depends on**: T5 · **Reuses**: T2
**Requirement**: QUA-02 · **Tests**: unit · **Gate**: quick
**Done when**: uso somado por tenant; quota excedida bloqueia.

### T28: Integrar medição/quota no copiloto

**What**: Medir cada chamada e bloquear com mensagem clara ao estourar a quota.
**Where**: `src/gestlog/copilot/` · **Depends on**: T17, T27 · **Reuses**: T27
**Requirement**: QUA-02 · **Tests**: integration · **Gate**: quick
**Done when**: quota bloqueia sem derrubar a sessão; uso registrado.

### T29: Golden set (formato + runner)

**What**: Formato do golden set por domínio e runner que reporta acurácia,
alucinação e fonte correta (com fake model nos testes).
**Where**: `src/gestlog/evaluation/`, `evals/` · **Depends on**: T17 · **Reuses**: T17
**Requirement**: QUA-01 · **Tests**: unit (fake model) · **Gate**: quick
**Done when**: runner produz relatório; teste com fake model passa.

### T30: Script de avaliação

**What**: Script/CLI para rodar o golden set contra o modelo real e salvar o relatório.
**Where**: `evals/`, `scripts/` · **Depends on**: T29 · **Reuses**: T29
**Requirement**: QUA-01 · **Tests**: integration · **Gate**: quick
**Done when**: script gera relatório com acurácia por domínio.

### T31: Gestão de usuários e papéis

**What**: Admin altera papel e remove usuários do tenant.
**Where**: `src/gestlog/web/`, `src/gestlog/auth/` · **Depends on**: T8 · **Reuses**: T8
**Requirement**: ADM-01 · **Tests**: integration · **Gate**: quick
**Done when**: mudança de papel reflete permissões; remoção revoga acesso.

### T32: Dashboard de KPIs

**What**: Tela com adoção, aceitação e cobertura de dados do tenant.
**Where**: `src/gestlog/web/` · **Depends on**: T5 · **Reuses**: T5, T22
**Requirement**: KPI-01 · **Tests**: integration · **Gate**: quick
**Done when**: KPIs agregados por tenant e período.

### T33: Testes de aceitação P1 (ponta a ponta)

**What**: Arquivo único de testes de aceitação cobrindo os critérios P1 (ACC-01..04,
ING-01..03, COP-01..06, SEC-01..03, QUA-01..02).
**Where**: `tests/acceptance/test_f1_mvp.py` · **Depends on**: todas as P1
**Reuses**: `conftest.fake_model_cls` · **Requirement**: todos P1
**Tests**: e2e · **Gate**: full
**Done when**: cada critério tem um teste; suíte completa verde com cobertura ≥ 80%.

---

## Parallel Execution Map

```
Phase 0:  T1 → T2
Phase 1:  T2 → T3 → T4 ; T3 → T5
Phase 2:  T4 → T6 → T7 → T8
Phase 3:  T7 → T9 → T10
Phase 4:  T11 [P] (após T2) ; T12 (T5,T11) → T13 (T10,T12)
Phase 5:  T14 [P] , T15 [P] , T16 [P] , T34 [P]  (após T5)
Phase 6:  T17 (T14-16,T34) → T18 (T17,T7) → { T19 (T10,T18) ; T20 (T18) }
Phase 7:  T21 (T17) → T22 (T21) → T23 (T19,T22)
Phase 8:  T24 [P] (T1) → T25 (T17,T24) ; T26 (T5,T17)
Phase 9:  T27 (T5) → T28 (T17,T27)
Phase 10: T29 (T17) → T30 (T29)
Phase 11: T31 (T8) ; T32 (T5)
Phase 12: T33 (todos P1)
```

**Constraint**: tarefas `[P]` só rodam em paralelo se o tipo de teste for
parallel-safe (unit). Integração/e2e são sempre sequenciais (Testing.md).

---

## Task Granularity Check

| Task | Scope | Status |
| --- | --- | --- |
| T1 deps | 1 arquivo | ✅ |
| T2 config | 1 módulo | ✅ |
| T3 modelos | 1 módulo coeso (schema) | ✅ |
| T4 migration | 1 artefato | ✅ |
| T5 repositórios | 1 módulo coeso | ✅ |
| T6 auth | 1 integração | ✅ |
| T7 tenancy guards | 1 módulo | ✅ |
| T8 onboarding | 1 fluxo | ✅ |
| T9 shell | 1 app factory | ✅ |
| T10 home | 1 página | ✅ |
| T11 parsers | 1 módulo | ✅ |
| T12 import service | 1 serviço | ✅ |
| T13 upload UI | 1 tela | ✅ |
| T14–T16 tools | 1 módulo cada | ✅ |
| T34 tool comum | 1 módulo compartilhado | ✅ |
| T17 copilot | 1 serviço | ✅ |
| T18 SSE | 1 endpoint | ✅ |
| T19 chat UI | 1 tela | ✅ |
| T20 histórico | 1 fluxo | ✅ |
| T21 recomendação | 1 módulo | ✅ |
| T22 feedback API | 1 endpoint | ✅ |
| T23 feedback UI | 1 componente | ✅ |
| T24 PII | 1 módulo | ✅ |
| T25 wire PII | 1 integração | ✅ |
| T26 auditoria/retenção | 1 módulo coeso | ✅ |
| T27 metering | 1 módulo | ✅ |
| T28 wire metering | 1 integração | ✅ |
| T29 golden set | 1 módulo | ✅ |
| T30 eval script | 1 script | ✅ |
| T31 admin | 1 fluxo | ✅ |
| T32 dashboard | 1 tela | ✅ |
| T33 acceptance | 1 arquivo | ✅ |

## Diagram-Definition Cross-Check

| Task | Depends (body) | Diagram | Status |
| --- | --- | --- | --- |
| T2 | T1 | T1→T2 | ✅ |
| T3 | T2 | T2→T3 | ✅ |
| T4 | T3 | T3→T4 | ✅ |
| T5 | T3 | T3→T5 | ✅ |
| T6 | T4 | T4→T6 | ✅ |
| T7 | T6 | T6→T7 | ✅ |
| T8 | T7 | T7→T8 | ✅ |
| T9 | T7 | T7→T9 | ✅ |
| T10 | T9 | T9→T10 | ✅ |
| T11 | T2 | T2→T11 | ✅ |
| T12 | T5,T11 | T5→T12, T11→T12 | ✅ |
| T13 | T10,T12 | T10→T13, T12→T13 | ✅ |
| T14–T16 | T5 | T5→T14/15/16 | ✅ |
| T34 | T5 | T5→T34 | ✅ |
| T17 | T14,T15,T16,T34 | →T17 | ✅ |
| T18 | T17,T7 | →T18 | ✅ |
| T19 | T10,T18 | →T19 | ✅ |
| T20 | T18 | →T20 | ✅ |
| T21 | T17 | T17→T21 | ✅ |
| T22 | T21 | T21→T22 | ✅ |
| T23 | T19,T22 | T19,T22→T23 | ✅ |
| T24 | T1 | T1→T24 | ✅ |
| T25 | T17,T24 | →T25 | ✅ |
| T26 | T5,T17 | →T26 | ✅ |
| T27 | T5 | T5→T27 | ✅ |
| T28 | T17,T27 | →T28 | ✅ |
| T29 | T17 | T17→T29 | ✅ |
| T30 | T29 | T29→T30 | ✅ |
| T31 | T8 | T8→T31 | ✅ |
| T32 | T5 | T5→T32 | ✅ |
| T33 | todos P1 | →T33 | ✅ |

## Test Co-location Validation

| Task | Layer created | Matrix requires | Task says | Status |
| --- | --- | --- | --- | --- |
| T1 | deps | none | none | ✅ |
| T2 | config | unit | unit | ✅ |
| T3 | models | integration | integration | ✅ |
| T4 | migration | integration | integration | ✅ |
| T5 | repositories | integration | integration | ✅ |
| T6 | auth | integration | integration | ✅ |
| T7 | auth/tenancy | integration | integration | ✅ |
| T8 | web/auth | integration | integration | ✅ |
| T9 | web | integration | integration | ✅ |
| T10 | web | integration | integration | ✅ |
| T11 | ingestion | unit | unit | ✅ |
| T12 | ingestion/repo | integration | integration | ✅ |
| T13 | web | integration | integration | ✅ |
| T14–T16 | tools | unit | unit | ✅ |
| T34 | tools/common | unit | unit | ✅ |
| T17 | copilot | unit | unit | ✅ |
| T18 | web/SSE | integration | integration | ✅ |
| T19 | web | integration | integration | ✅ |
| T20 | copilot/web | integration | integration | ✅ |
| T21 | copilot | unit | unit | ✅ |
| T22 | web/repo | integration | integration | ✅ |
| T23 | web | integration | integration | ✅ |
| T24 | privacy | unit | unit | ✅ |
| T25 | copilot | unit | unit | ✅ |
| T26 | audit/repo | integration | integration | ✅ |
| T27 | metering | unit | unit | ✅ |
| T28 | copilot | integration | integration | ✅ |
| T29 | evaluation | unit | unit | ✅ |
| T30 | evaluation script | integration | integration | ✅ |
| T31 | web/auth | integration | integration | ✅ |
| T32 | web | integration | integration | ✅ |
| T33 | acceptance | e2e | e2e | ✅ |

---

## Open Decisions Before Execution

- Formato exato do golden set (T29) e política de upsert da importação (T12).
- Estratégia de DB nos testes de integração (SQLite em memória vs. container Postgres no CI).
