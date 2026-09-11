# State

**Last Updated:** 2026-09-11
**Current Work:** F1 (MVP) — planejamento concluído (`spec`/`design`/`tasks`), aguardando aprovação para executar

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
**Impact:** planejamento guiado por `.specs/project/ROADMAP.md`.

### AD-007: Stack da F1 (FastAPI + Jinja/HTMX + Postgres + FastAPI Users) (2026-09-11)

**Decision:** backend FastAPI; UI SSR com Jinja2 + HTMX + SSE; Postgres único com
`tenant_id`; autenticação self-hosted com FastAPI Users; copiloto reaproveita o
grafo LangGraph existente.
**Reason:** máxima reutilização do core Python/LangGraph, mínimo de peças para dev
solo, isolamento por tenant simples e padrão de mercado.
**Trade-off:** SSR/HTMX é menos flexível que uma SPA; migrar para SPA depois custa.
**Impact:** tasks T1–T33 em `.specs/features/f1-mvp/tasks.md` seguem esse stack.

### AD-008: Nomenclatura — Empresa (tenant) em português (2026-09-11)

**Decision:** no código, usar `Empresa`/`empresa_id` (modelo, tabela e colunas) em
vez de `Tenant`/`tenant_id`, seguindo a convenção de nomes em português do `AGENTS.md`.
**Reason:** consistência com o restante do código (tools, repositórios, docstrings).
**Trade-off:** afasta do vocabulário SaaS em inglês; docs mantêm "tenant" entre parênteses.
**Impact:** migration inicial regenerada com tabela `empresa`; AD-007 e specs usam
"tenant" como termo de domínio, "Empresa" como nome de código.

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

---

## Deferred Ideas

- [ ] Benchmarking anonimizado entre tenants — Captured during: definição de produto
- [ ] Marketplace de conectores de terceiros — Captured during: definição de produto
- [ ] Novos domínios (contratos, devoluções, inventário) — Captured during: definição de produto

---

## Todos

- [ ] Executar a F1 (T1–T33) após aprovação; começar por T1/T2.
- [ ] Calibrar metas numéricas dos KPIs após primeiras semanas de uso.
