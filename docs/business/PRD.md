# PRD — gestlog

**Versão:** 0.1 (rascunho aprovado)
**Data:** 2026-09-11
**Status:** Aprovado para orientar o roadmap
**Owner:** Time gestlog (dev solo)
**Artefatos relacionados:** `.specs/project/PROJECT.md`, `.specs/project/ROADMAP.md`, `.specs/project/STATE.md`

---

## 1. Visão geral

**gestlog** é um **copiloto de decisão logística** SaaS multi-cliente, acessado
via aplicação web com chat, em português. Ele recebe dados operacionais de uma
empresa-cliente (estoque, transporte, fornecedores), combina com ferramentas de
cálculo/consulta e **recomenda decisões explicadas** ao operador logístico.

No MVP o gestlog **não executa ações** nos sistemas de origem: ele recomenda e
justifica; o humano decide e executa. Essa fronteira read-only é uma decisão de
segurança e de prazo, não uma limitação técnica permanente.

> Estado atual: o repositório já contém o núcleo do produto — grafo LangGraph
> com supervisor + especialistas (transporte, fornecedores, estoque) e tools
> determinísticas. O MVP **evolui** esse núcleo, não recomeça. Ver Anexo B.

---

## 2. Problema e oportunidade

**Problema.** Em PMEs de logística, a informação necessária para decidir (nível
de estoque, prazo/atraso de uma entrega, desempenho de um fornecedor) está
espalhada em planilhas e sistemas desconectados. O operador gasta tempo
consolidando dados e depende de experiência tácita para decidir **o que** e
**quando** repor, **qual** fornecedor acionar e **como** priorizar entregas.

**Oportunidade.** Um copiloto conversacional, alimentado pelos dados do próprio
cliente, reduz esse tempo e padroniza a decisão — sem exigir que a PME troque de
TMS/ERP/WMS nem implante integrações complexas de início.

---

## 3. Público-alvo e personas

**ICP (MVP):** transportadoras e operadores logísticos de **pequeno e médio
porte**, sem TI próprio relevante, que hoje operam em planilha. Onboarding por
importação de dados.

| Persona | Papel | Objetivo | Dor principal |
|---|---|---|---|
| **Operador logístico** (usuário primário) | Executa o dia a dia | Decidir rápido sobre reposição, frete, fornecedor e atrasos | Consolidar dados dispersos e confiar na decisão |
| **Gestor de logística** (usuário secundário) | Administra a conta | Enxergar qualidade dos dados e adoção | Não saber se o time usa a ferramenta nem se os dados estão completos |
| **Admin da conta** (cliente) | Configura e convida usuários | Gerenciar acesso e importações | Onboarding e controle de acesso simples |

**Multi-tenancy:** cada empresa-cliente é um **tenant** independente; dados e
usuários isolados por tenant.

---

## 4. Proposta de valor

- **Uma pergunta, uma recomendação explicada** — em vez de abrir vários sistemas.
- **Rastreável** — toda recomendação cita a fonte/dado que a sustenta.
- **Sem trocar de sistema** — começa com dados que a PME já tem (planilha/CSV).
- **Seguro por padrão** — read-only no MVP; nenhuma alteração silenciosa nos
  sistemas do cliente.

**Diferenciais:** foco em *decisão* (não só consulta); pt-BR; onboarding leve;
isolamento e LGPD desde o desenho.

---

## 5. Objetivos e métricas de sucesso (KPIs)

| Objetivo | KPI | Alvo do MVP (a calibrar) |
|---|---|---|
| Reduzir o tempo para decidir | Tempo médio até a decisão vs. processo atual | Redução mensurável em uso real |
| Recomendações úteis | % de recomendações aceitas pelo operador | ≥ 60% |
| Impacto operacional | Redução de ruptura de estoque e de entregas atrasadas atribuível ao uso | Tendência de melhora |
| Qualidade da IA | Acurácia em golden set por domínio; taxa de alucinação; fonte citada correta | Acurácia alta e alucinação ~0 em golden set |

> As metas numéricas serão recalibradas após as primeiras semanas de uso real.

---

## 6. Escopo do MVP

### 6.1 Incluído

- App web com chat autenticado por **conta por empresa** (tenant) + login.
- **4 domínios de decisão** (read-only): reposição de estoque, seleção de
  fornecedor, custo/prazo de frete, priorização de atrasos.
- **Ingestão por importação** (CSV/planilha), com validação e status.
- **Recomendação explicada** com fonte, e captura de **aceitação/descarte**.
- **LGPD**: redação de PII antes do LLM, retenção configurável, sem treino em
  dados do cliente, provedor com DPA/zero-retention.
- **LLM hospedado** pela plataforma, com medição de uso por tenant.

### 6.2 Fora do MVP (não-objetivos)

- **Execução de ações / escrita** nos sistemas de origem (entra na F2/HITL).
- **Integrações de API em tempo real** com TMS/ERP/WMS (F3).
- **Enterprise**: SSO corporativo, billing/planos, app mobile (F5).
- **Alertas proativos / automação em background** (F4) — o produto é puxado pelo
  usuário no MVP.
- **BYO-LLM / on-prem / multi-idioma** (F5).
- Domínio de **cadastros incompletos** (F2, pois o valor está na correção/escrita).

---

## 7. Requisitos funcionais (MVP)

| ID | Requisito | Domínio |
|---|---|---|
| FR-01 | Criar/gerenciar conta de empresa (tenant) e convidar usuários | Conta |
| FR-02 | Autenticar usuário (login) e autorizar por tenant (isolamento) | Conta |
| FR-03 | Papéis mínimos: **admin da conta** e **operador** | Conta |
| FR-04 | Importar dados de estoque, transporte e fornecedores (CSV/planilha) | Ingestão |
| FR-05 | Validar e normalizar os dados na entrada; reportar erros por linha | Ingestão |
| FR-06 | Exibir status/histórico de importação e o que entrou | Ingestão |
| FR-07 | Receber pergunta em linguagem natural e rotear ao domínio adequado (supervisor) | Copiloto |
| FR-08 | Responder nos 4 domínios do MVP com ferramentas read-only | Copiloto |
| FR-09 | Apresentar **recomendação + justificativa + fonte** do dado | Copiloto |
| FR-10 | Permitir **aceitar/descartar** a recomendação (insumo dos KPIs) | Copiloto |
| FR-11 | Manter histórico da conversa por usuário/tenant | Copiloto |
| FR-12 | Informar quando o dado é insuficiente, em vez de inventar | Copiloto |
| FR-13 | Avaliar qualidade por **golden set** por domínio (humano no loop) | Qualidade |
| FR-14 | Aplicar limite/quota de uso de LLM por tenant | Custo |
| FR-15 | Registrar logs/auditoria por tenant (pergunta, recomendação, aceite) | Observabilidade |

---

## 8. Requisitos não-funcionais

| ID | Requisito |
|---|---|
| NFR-01 | Latência: **p95 da recomendação < 15s** (uso interativo via chat) |
| NFR-02 | Escala do MVP: **~dezenas de tenants**, poucos usuários cada |
| NFR-03 | Isolamento de dados por tenant em todas as consultas e logs |
| NFR-04 | Segurança: TLS em trânsito, criptografia em repouso, segredos fora do código |
| NFR-05 | LGPD: redação de PII antes do LLM; retenção configurável; sem treino em dados do cliente; DPA/zero-retention do provedor |
| NFR-06 | Disponibilidade best-effort no MVP (sem SLA) |
| NFR-07 | Custo de LLM medido e atribuível por tenant |
| NFR-08 | Idioma pt-BR; acessibilidade básica da web |
| NFR-09 | Observabilidade: métricas de uso, custo e qualidade por tenant |

---

## 9. Jornadas principais

**J1 — Onboarding (admin).** Cria a conta → convida operadores → importa
planilhas (estoque/transporte/fornecedores) → vê o status e corrige erros.

**J2 — Decisão (operador).** Pergunta em linguagem natural → recebe recomendação
com justificativa e fonte → aceita ou descarta → (no MVP) executa no sistema de
origem.

**J3 — Gestão (gestor).** Acompanha adoção, aceitação das recomendações e
qualidade/cobertura dos dados importados.

---

## 10. Arquitetura e restrições técnicas

- **Evolução do código atual**: mantém o núcleo LangGraph (supervisor
  `with_structured_output` + especialistas ReAct + tools) e adiciona:
  **API (FastAPI)**, **app web com chat**, **autenticação/tenancy** e **ingestão
  de arquivos**.
- **LLM** via endpoint compatível com OpenAI, **hospedado pela plataforma**;
  configuração por ambiente (mantém `Settings`/pydantic-settings).
- **Sem novas dependências** sem justificativa; `pyproject.toml` é a fonte de
  verdade.
- Convenções do repositório (`AGENTS.md`): `from __future__ import annotations`,
  black 88, ruff, `logger` em vez de `print`, docstrings em português, testes com
  o modelo fake (sem rede).

---

## 11. Dados, privacidade e LGPD

- **Classes tratadas:** operacional de estoque, transporte, fornecedores e **PII
  de clientes** (destinatários).
- **PII** é minimizada/redigida **antes** de ser enviada ao LLM.
- **Retenção** configurável por tenant; **sem treinamento** com dados do cliente.
- **Sub-processador de LLM** exige DPA e política de zero-retention.
- **Auditoria** por tenant (FR-15) como base para conformidade.

---

## 12. Roadmap por fases

| Fase | Tema | Entrega principal |
|---|---|---|
| **F1 — MVP** | Copiloto read-only | Web + contas + importação + 4 domínios + KPIs |
| **F2 — HITL** | Escrita com aprovação | Corrigir/completar **cadastros incompletos** e documentos, com aprovação; feedback loop |
| **F3 — Integrações** | Dados em tempo real | Conectores de API por tenant (TMS/ERP/WMS) |
| **F4 — Proativo** | Alertas | Monitoramento e notificações (estoque baixo, atraso, fornecedor degradando) |
| **F5 — Enterprise** | Escala/opções | SSO, billing/planos, mobile, BYO-LLM/on-prem, multi-idioma |

Detalhamento em `.specs/project/ROADMAP.md`.

---

## 13. Riscos e mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| Dados importados incompletos/errados → recomendação ruim | Alto | Validação na entrada (FR-05), aviso de dado insuficiente (FR-12), golden set |
| Vazamento de PII para o LLM | Alto | Redação de PII (NFR-05), DPA/zero-retention |
| Vazamento entre tenants | Alto | Isolamento por `tenant_id` (NFR-03) e testes dedicados |
| Latência acima do alvo | Médio | Streaming/caching, medir p95 (NFR-01) |
| Custo de LLM imprevisível | Médio | Quotas por tenant (FR-14/NFR-07) |
| Escopo crescer (cadastros, alerts) no MVP | Médio | Não-objetivos explícitos (§6.2); ideias adiadas em STATE.md |
| Sem git/repo estruturado | Médio | Inicializar repo, branch/PR e `gitignore` (bloqueio em STATE.md) |

---

## 14. Decisões em aberto

1. Stack exata da camada web (ex.: templates server-side vs. SPA) — decidir no
   design da F1.
2. Modelo de dados de tenancy (coluna `tenant_id` vs. schema por tenant) —
   decidir no design da F1.
3. Metas numéricas dos KPIs — calibrar após primeiras semanas de uso.
4. Formato preciso do golden set por domínio.

---

## Anexo A — Glossário

- **Tenant:** empresa-cliente isolada no SaaS.
- **Copiloto de decisão:** assistente que recomenda e explica, sem executar.
- **HITL (Human-in-the-loop):** humano aprova antes de qualquer escrita.
- **Domínio:** área de decisão (estoque, fornecedor, frete, atrasos).
- **Golden set:** conjunto de perguntas/casos com resposta esperada, para avaliar
  a qualidade da IA.

---

## Anexo B — Estado atual do código (baseline)

- `src/gestlog/graph.py` — grafo supervisor + especialistas (`SPECIALISTS`).
- `src/gestlog/agents/` — `supervisor`, `base` (loop ReAct) e 3 especialistas.
- `src/gestlog/tools/` — tools determinísticas de transporte, fornecedores e
  estoque (dados mockados, andaime até TMS/ERP/WMS).
- `src/gestlog/config.py` — `Settings` (pydantic-settings) + `get_settings()`.
- `src/gestlog/cli.py` — REPL (interface de dev; substituída pela web na F1).
- Testes: **17 passando, ~99% de cobertura** (`uv run pytest`).
