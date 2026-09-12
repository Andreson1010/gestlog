# State

**Last Updated:** 2026-09-12
**Current Work:** F1 (MVP) — em execução na branch `feat/f1-mvp`; Fase 1 (T1–T5) concluída, catálogo de tools fechado (AD-010), docs versionados (AD-011), estrutura definida (AD-012) e T6 (login/logout) concluído; T7–T8 pendentes

---

## Recent Decisions (Last 60 days)

### AD-001: Produto SaaS multi-cliente, web, para PMEs de logística (2026-09-11)

**Decision:** gestlog é SaaS multi-cliente, acessado por app web com chat; ICP =
transportadoras/operadores PME sem TI próprio; idiom pt-BR.
**Reason:** é a dor validada (dados dispersos em planilha) e o formato do código
atual (supervisor + especialistas conversacionais).
**Trade-off:** SaaS traz tenancy, auth e LGPD para o MVP, aumentando o escopo.
**Impact:** F1 precisa de conta por empresa, login e isolamento por `tenant_id`.

### AD-002: Copiloto read-only no MVP; escrita só na F2 via HITL (2026-09-11)

**Decision:** no MVP o gestlog apenas recomenda e explica; nenhuma escrita nos
sistemas de origem. Escrita entra na F2 com aprovação humana.
**Reason:** segurança e prazo; a dor de cadastros incompletos exige correção, mas
o valor da escrita só se justifica depois do núcleo read validado.
**Trade-off:** adia o valor de correção (F2) em troca de um MVP seguro.
**Impact:** todos os requisitos do MVP são de leitura; a arquitetura HITL fica
desenhada para a F2.

### AD-003: Dados por importação agora, conectores de API depois (2026-09-11)

**Decision:** MVP importa CSV/planilha; integrações de API por tenant são a F3.
**Reason:** entrega valor sem depender de cada TMS/ERP/WMS do cliente.
**Trade-off:** dados não são em tempo real no MVP.
**Impact:** F1 inclui ingestão com validação; F3 substitui/complementa.

### AD-004: LLM hospedado pela plataforma, medido por tenant (2026-09-11)

**Decision:** a plataforma hospeda e paga o LLM (endpoint OpenAI-compatível) e
mede uso por tenant; BYO-LLM/on-prem fica para a F5.
**Reason:** simplicidade de onboarding e controle de custo/experiência.
**Trade-off:** custo de LLM vira custo da plataforma; exige quotas (FR-14).
**Impact:** NFR-07 e FR-14 no MVP.

### AD-005: LGPD sério com redação de PII antes do LLM (2026-09-11)

**Decision:** PII de clientes é tratada; minimizada/redigida antes de ir ao LLM;
retenção configurável; sem treino em dados do cliente; provedor com
DPA/zero-retention.
**Reason:** PII está no escopo (destinatários) e o LLM é de terceiros.
**Trade-off:** redação adiciona complexidade à pipeline.
**Impact:** NFR-05 e requisito de auditoria por tenant.

### AD-006: Roadmap por fases sem datas; execução solo (2026-09-11)

**Decision:** fases M1–M5 sem calendário; critérios de saída por fase.
**Reason:** execução individual.
**Trade-off:** menos previsibilidade de datas externa.
**Impact:** planejamento guiado por `docs/specs/project/ROADMAP.md`.

### AD-007: Stack da F1 (FastAPI + Jinja/HTMX + Postgres + FastAPI Users) (2026-09-11)

**Decision:** backend FastAPI; UI SSR com Jinja2 + HTMX + SSE; Postgres único com
`tenant_id`; autenticação self-hosted com FastAPI Users; copiloto reaproveita o
grafo LangGraph existente.
**Reason:** máxima reutilização do core Python/LangGraph, mínimo de peças para dev
solo, isolamento por tenant simples e padrão de mercado.
**Trade-off:** SSR/HTMX é menos flexível que uma SPA; migrar para SPA depois custa.
**Impact:** tasks T1–T33 em `docs/specs/features/f1-mvp/tasks.md` seguem esse stack.

### AD-008: Nomenclatura — Empresa (tenant) em português (2026-09-11)

**Decision:** no código, usar `Empresa`/`empresa_id` (modelo, tabela e colunas) em
vez de `Tenant`/`tenant_id`, seguindo a convenção de nomes em português do `AGENTS.md`.
**Reason:** consistência com o restante do código (tools, repositórios, docstrings).
**Trade-off:** afasta do vocabulário SaaS em inglês; docs mantêm "tenant" entre parênteses.
**Impact:** migration inicial regenerada com tabela `empresa`; AD-007 e specs usam
"tenant" como termo de domínio, "Empresa" como nome de código.

### AD-009: Catálogo de ferramentas da F1 (2026-09-11)

**Decision:** formalizar um "Catálogo de ferramentas (F1)" no `design.md` antes da
Fase 5, com 4 tools read-only novas (`listar_entregas_atrasadas`,
`comparar_fornecedores`, `listar_abaixo_minimo`, `dias_de_cobertura`) além das 9
existentes. Tools de cadastros (read/sugerir) e de escrita (HITL) ficam para a F2.
**Reason:** os agentes precisam de tools de busca e comparação para recomendar nos
4 domínios; decidir capacidade é papel do design, não do Execute.
**Trade-off:** exige tabelas de apoio (movimentações de estoque, histórico de
fornecedor, datas de previsão/entrega no transporte).
**Impact:** adicionar tasks ao `tasks.md` da F1. **Pendente:** o usuário indicou que
tem tools próprias a incluir — capturar antes de fechar o catálogo.
**Status:** ✅ resolvida em 2026-09-12 pela AD-010; as 4 tools provisórias foram
substituídas por tools nomeadas (mapeamento no `design.md`).

### AD-010: Inventário real de tools do usuário (2026-09-12)

**Decision:** adotar como catálogo canônico no `design.md` o inventário fornecido
pelo usuário — 1 tool comum (`enviar_resposta_logistica`) + tools por domínio
(estoque, transporte, fornecedores). A F1 implementa **apenas leitura/análise**;
as de **escrita/ação** ficam registradas para a F2 com HITL. Nomes em português
(AD-008). As 4 tools provisórias da AD-009 foram substituídas por tools nomeadas.
Nova task **T34** (tool comum); T14–T16 ampliadas.
**Reason:** o usuário especificou as tools dos especialistas; a F1 é read-only
(AD-002), então só entram leitura/análise.
**Trade-off:** exige tabelas de apoio para análise (movimentações, histórico) e a
tool comum altera o binding de tools dos três especialistas.
**Impact:** `design.md` §"Catálogo de ferramentas (F1)"; `tasks.md` T14–T16 + T34;
T17 passa a depender de T34.

### AD-011: Docs-as-code — documentação em `docs/`, versionada (2026-09-12)

**Decision:** isolar o contexto conceitual do código executável: specs/planejamento
passam de `.specs/` para `docs/specs/` (ao lado de `docs/business/`), e `docs/` é
**versionado** no git. Nada de docs em `.gitignore`. Referências atualizadas em
`docs/` e no scaffold `.opencode/`.
**Reason:** organização docs-as-code; docs e código vivem no mesmo repo, mas em
árvores separadas e revisáveis.
**Trade-off:** commits passam a misturar código e documentação; sem impacto técnico.
**Impact:** estrutura macro do repo = `src/` (executável) + `docs/` (conceitual) +
`tests/`; `.specs/` deixa de existir.

### AD-012: Pacote único com fronteiras conceituais (não monorepo) (2026-09-12)

**Decision:** manter um **único pacote** (`src/gestlog/`) no F1, organizado em três
fronteiras conceituais: `apps` (entrada/deploy: `cli.py`, `web/`, `auth/`,
`copilot/`), `agents` (grafo e domínio: `graph.py`, `state.py`, `agents/`, `tools/`)
e `libs` (fundação: `config.py`, `llm.py`, `db/`, `repositories/`). Direção de
dependência `apps → agents → libs` (+ `apps → libs`), nunca invertida. `db/` +
`repositories/` são a única porta de SQL.
**Reason:** driver é **clareza**, não deploy independente. O gestlog é um único
deployable e o multiagente roda in-process (nós do LangGraph, não serviços). Um
monorepo multi-pacote traria workspace uv, múltiplos `pyproject`, tooling de
fronteiras e refatoração de T1–T5 sem consumidor que justifique.
**Trade-off:** fronteiras são convenção (não impostas por ferramenta); exige
disciplina de imports.
**Impact:** `AGENTS.md` §"Estrutura e fronteiras" vira a fonte de verdade de onde
cada coisa mora. **Gatilho de migração:** extrair para pacotes só quando houver
deploy/escala independentes (ex.: worker de alertas da F4 ou UI como app próprio),
de forma incremental (`libs/*` → `agents/` → `apps/`).

### AD-013: Camada async isolada para o auth (FastAPI Users) (2026-09-12)

**Decision:** o FastAPI Users 15 só oferece `SQLAlchemyUserDatabase` com
`AsyncSession`. Adicionar `build_async_engine`/`build_async_session_factory`/
`init_async_db` em `libs/db` e concentrar o uso de `AsyncSession` na camada de auth
(`auth/db.py`). Repositórios e copilot seguem **sync**. `aiosqlite` entra como dep
de dev (testes); em produção o engine async usa o mesmo `DATABASE_URL`
(`postgresql+psycopg`).
**Reason:** menor custo que refatorar T3–T5 para async, mantendo FastAPI Users
nativo.
**Trade-off:** duas camadas de sessão (sync + async) e dois pools na mesma app.
**Impact:** T6; `config.py` ganha `auth_cookie_name`/`auth_cookie_secure`;
`AGENTS.md` §"Estrutura e fronteiras" (libs sync, apps pode async).

---

## Active Blockers

Nenhum bloqueio ativo.

_(B-001 — repositório não era git — resolvido em 2026-09-11: `git init -b main`,
`.gitignore` atualizado, commit raiz `31c7368` e remote `origin` publicado em
https://github.com/Andreson1010/gestlog (privado).)_

---

## Lessons Learned

### L-001: Artefatos opencode devem ser agnósticos

**Context:** scaffold `.opencode/` foi copiado do projeto medasist.
**Problem:** skills e agentes vinham com paths e regras específicas do medasist.
**Solution:** generalizados para descobrir comandos/padrões via `AGENTS.md`;
especificidades do projeto ficam no `AGENTS.md`.
**Prevents:** retrabalho ao reutilizar o scaffold em outros projetos.

---

## Quick Tasks Completed

| #   | Description | Date | Commit | Status |
| --- | ----------- | ---- | ------ | ------ |
| 001 | Copiar e generalizar `.opencode/` (skills, agentes, commands) + `CONTEXT.md` | 2026-09-11 | — (sem git) | ✅ Done |
| 002 | Escrever PRD + artefatos TLC (`PROJECT`/`ROADMAP`/`STATE`) | 2026-09-11 | — (sem git) | ✅ Done |
| 003 | Inicializar git e commit raiz | 2026-09-11 | 31c7368 | ✅ Done |
| 004 | Configurar remote `origin` e publicar `main` | 2026-09-11 | 871f0be | ✅ Done |
| 005 | Planejar F1 (spec/design/tasks + TESTING) | 2026-09-11 | — | ✅ Done |
| 006 | Executar F1 Fase 1 (T1–T5) + rename `Tenant`→`Empresa` | 2026-09-11 | 8438baa | ✅ Done |
| 007 | Capturar inventário de tools e formalizar catálogo F1 (AD-010) | 2026-09-12 | — | ✅ Done |
| 008 | Reorganizar docs-as-code: `.specs/` → `docs/specs/` e versionar (AD-011) | 2026-09-12 | — | ✅ Done |
| 009 | Definir fronteiras do pacote único (AD-012) e camada async do auth (AD-013) | 2026-09-12 | — | ✅ Done |
| 010 | Executar F1 Fase 2 — T6 login/logout por cookie (FastAPI Users) | 2026-09-12 | — | ✅ Done |

---

## Deferred Ideas

- [x] **Tools específicas do usuário** — capturadas em 2026-09-12 (AD-010) — Captured during: F1
- [x] Catálogo de tools F1 — fechado no `design.md` (AD-010); substitui as 4 provisórias da AD-009 — Captured during: F1
- [ ] Tools de escrita/ação (HITL): estoque (`gerenciar_inventario`, `gerenciar_qualidade`, `escalar_operacoes`), transporte (`organizar_envio`, `coordenar_operacoes`, `gerenciar_manuseio_especial`, `processar_devolucoes`, `gerenciar_disrupcoes`), fornecedores (`tratar_conformidade` ação) e envio externo de `enviar_resposta_logistica` — Captured during: F2
- [ ] Tools de comparação de rotas/modal — Captured during: F1/F2
- [ ] Benchmarking anonimizado entre tenants — Captured during: definição de produto
- [ ] Marketplace de conectores de terceiros — Captured during: definição de produto
- [ ] Novos domínios (contratos, devoluções, inventário) — Captured during: definição de produto

---

## Todos

- [ ] Executar a F1 Fase 2 (T6 auth → T7 guards → T8 onboarding).
- [ ] Calibrar metas numéricas dos KPIs após primeiras semanas de uso.
