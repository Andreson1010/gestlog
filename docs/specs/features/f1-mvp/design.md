# F1 — MVP do gestlog (copiloto read-only) — Design

**Spec**: `docs/specs/features/f1-mvp/spec.md`
**Status**: Draft (awaiting approval)

---

## Architecture Overview

Aplicação web única (FastAPI) que serve páginas SSR (Jinja2 + HTMX) e endpoints
HTMX/SSE. A camada de copiloto reaproveita o grafo LangGraph existente,
envelopado por um serviço que injeta contexto do tenant, redige PII, mede uso e
persiste a conversa. Postgres guarda tenants, usuários, dados importados,
conversas, recomendações, auditoria e uso.

```mermaid
graph TD
    Browser[Navegador: Jinja + HTMX + SSE] --> Web[FastAPI: rotas web e HTMX]
    Web --> Auth[FastAPI Users: sessão/login]
    Web --> Ingest[Ingestão: upload e validação]
    Web --> Copilot[Copilot Service]
    Copilot --> PII[Redação de PII]
    Copilot --> Graph[Grafo LangGraph existente]
    Copilot --> Meter[Medição/quota LLM]
    Copilot --> Repo[(Postgres: SQLAlchemy)]
    Ingest --> Repo
    Auth --> Repo
    Graph --> LLM[LLM hospedado OpenAI-compat]
    Meter --> Repo
    Web --> Audit[Auditoria]
    Audit --> Repo
```

---

## Code Reuse Analysis

### Existing Components to Leverage

| Component | Location | How to Use |
| --- | --- | --- |
| Grafo supervisor + especialistas | `src/gestlog/graph.py` | Chamar `build_graph`/`run_query` a partir do Copilot Service |
| Especialistas e prompts | `src/gestlog/agents/` | Reusar sem alterar; o domínio já existe |
| Tools read-only | `src/gestlog/tools/` | Reusar; trocar o backend mock pelo dado importado do tenant |
| Config | `src/gestlog/config.py` | Estender `Settings` (DB, auth, retenção, quotas) |
| Fábrica de modelo | `src/gestlog/llm.py` | Reusar `build_chat_model` |
| Estado do grafo | `src/gestlog/state.py` | Reusar `AgentState` |
| Testes com modelo fake | `tests/conftest.py` | Reusar `fake_model_cls`; nenhum teste toca rede |
| Convenções | `AGENTS.md` | Manter estilo, black/ruff, docstrings em pt-BR |

### Integration Points

| System | Integration Method |
| --- | --- |
| LLM | Endpoint OpenAI-compatível via `ChatOpenAI` (já existente) |
| Banco | Postgres via SQLAlchemy 2.x + Alembic (novo) |
| Autenticação | FastAPI Users (novo), sessão por cookie |
| Dados do cliente | Importação CSV/planilha no MVP (F3 substitui por API) |

---

## Components

### Web app (FastAPI)

- **Purpose**: servir páginas SSR e endpoints HTMX/SSE, autenticados.
- **Location**: `src/gestlog/web/`
- **Interfaces**: rotas `/login`, `/conta`, `/importar`, `/chat`, `/chat/stream` (SSE), `/recomendacoes`.
- **Dependencies**: FastAPI, Jinja2, HTMX, FastAPI Users, SQLAlchemy.
- **Reuses**: nada existente de web (novo).

### Auth & Tenancy

- **Purpose**: login, sessão, papéis e resolução do `tenant_id` por requisição.
- **Location**: `src/gestlog/auth/`
- **Interfaces**: `get_current_user()`, `get_current_tenant()`, dependências FastAPI; guardas de acesso.
- **Dependencies**: FastAPI Users, SQLAlchemy.
- **Reuses**: `Settings`.

### Ingestão

- **Purpose**: receber CSV/planilha, validar/normalizar e persistir por tenant.
- **Location**: `src/gestlog/ingestion/`
- **Interfaces**: `import_dataset(tenant_id, tipo, file) -> ImportResult`; validadores por tipo.
- **Dependencies**: pandas/openpyxl (avaliar dependências), SQLAlchemy.
- **Reuses**: padrões do repositório.

### Copilot Service

- **Purpose**: receber pergunta, injetar dados do tenant nas tools, rodar o grafo,
  redigir PII, medir uso e persistir conversa/recomendação.
- **Location**: `src/gestlog/copilot/`
- **Interfaces**: `answer(tenant_id, user_id, question) -> stream[str]`.
- **Dependencies**: grafo existente, repositórios, `PII`, `Meter`.
- **Reuses**: `graph.build_graph`, `llm.build_chat_model`, `state.AgentState`.

### Data access do tenant (tools)

- **Purpose**: fazer as tools lerem os dados importados do tenant em vez do mock.
- **Location**: `src/gestlog/tools/` (adaptar) + `src/gestlog/repositories/`
- **Interfaces**: as mesmas assinaturas das tools atuais, agora com `tenant_id` no
  contexto.
- **Dependencies**: SQLAlchemy.
- **Reuses**: assinaturas/prompts atuais; **trocar o corpo**, não a estrutura
  (como o próprio `AGENTS.md` recomenda).

### PII Redaction

- **Purpose**: remover/minimizar PII antes de enviar texto ao LLM.
- **Location**: `src/gestlog/privacy/`
- **Interfaces**: `redact(text) -> RedactedText`; política por tenant.
- **Dependencies**: regex/allowlist (sem LLM).
- **Reuses**: —.

### Metering & Quota

- **Purpose**: medir tokens/uso por tenant e aplicar quota.
- **Location**: `src/gestlog/copilot/metering.py`
- **Interfaces**: `record_usage(tenant_id, tokens, model)`, `check_quota(tenant_id)`.
- **Dependencies**: SQLAlchemy, `Settings`.

### Avaliação (golden set)

- **Purpose**: executar golden set por domínio e reportar acurácia.
- **Location**: `evals/` (script) + `src/gestlog/evaluation/` (núcleo testável).
- **Interfaces**: `run_golden_set(dataset) -> EvalReport`.
- **Dependencies**: grafo, modelo.
- **Reuses**: `tests/conftest.py` fake model para testes.

### Persistência

- **Purpose**: modelos e migrations.
- **Location**: `src/gestlog/db/` + `alembic/`
- **Interfaces**: `Base`, sessão, repositórios.
- **Dependencies**: SQLAlchemy, Alembic, psycopg.

---

## Data Models

> Nomenclatura: "tenant" é o termo de domínio; no código o modelo/coluna chama-se
> `Empresa`/`empresa_id` (ver AD-008 no STATE.md).

```python
class Tenant:            # id, nome, criado_em, retencao_dias
class User:              # id, email, hash, ativo (FastAPI Users)
class Membership:        # user_id, tenant_id, papel (admin|operador|gestor)
class ImportJob:         # id, tenant_id, tipo, status, aceitas, rejeitadas, criado_em
class ImportError:       # id, import_job_id, linha, motivo
class StockItem:         # tenant_id, sku, nome, quantidade, minimo, local
class Supplier:          # tenant_id, fornecedor_id, nome, categoria, prazo_dias, avaliacao, ativo
class TransportRecord:   # tenant_id, origem, destino, peso_kg (dados de frete/rastreio)
class Conversation:      # id, tenant_id, user_id, criado_em
class Message:           # id, conversation_id, papel, conteudo_redigido, criado_em
class Recommendation:    # id, conversation_id, dominio, texto, justificativa, fontes(json)
class Feedback:          # id, recommendation_id, decisao(aceita|descartada), user_id, criado_em
class UsageRecord:       # id, tenant_id, modelo, tokens, criado_em
class AuditLog:          # id, tenant_id, user_id, evento, detalhe, criado_em
```

**Relationships**: tudo pendurado em `Tenant` via `tenant_id`; `Membership` liga
`User`↔`Tenant`; conversas → mensagens → recomendações → feedback.

---

## Catálogo de ferramentas (F1)

> Decisões AD-009/AD-010 no STATE.md. Nomes canônicos em **português** (AD-008). A
> F1 é **read-only** (AD-001): só entram tools de **leitura** e **análise**. As de
> **escrita/ação** ficam registradas para a **F2** com HITL (confirmação humana
> antes de mutar dados). A troca do mock pelo repositório do tenant preserva as
> **assinaturas** das tools existentes (Tech Decisions).

### Tool comum (todos os especialistas)

| Tool | Origem | F1 | F2 |
| --- | --- | --- | --- |
| `enviar_resposta_logistica` | `send_logistics_response` | compõe a resposta ao usuário (sem envio externo) | envio real a stakeholders (e-mail/API) |

Fonte única em `src/gestlog/tools/common.py`; os três especialistas a importam,
evitando duplicação.

### Estoque

| Tool | Origem | F1 / F2 |
| --- | --- | --- |
| `consultar_estoque` (existente) | — | F1 leitura |
| `calcular_reposicao` (existente) | — | F1 leitura |
| `listar_movimentacoes` (existente) | — | F1 leitura |
| `prever_demanda` | `forecast_demand` | F1 análise |
| `otimizar_armazem` | `optimize_warehouse` | F1 análise |
| `otimizar_custos` | `optimize-costs` | F1 análise |
| `gerenciar_inventario` | `manage_inventory` | F2 escrita (HITL) |
| `gerenciar_qualidade` | `manage_quality` | F2 escrita (HITL) |
| `escalar_operacoes` | `scale operations` | F2 escrita (HITL) |

### Transporte

| Tool | Origem | F1 / F2 |
| --- | --- | --- |
| `calcular_frete` (existente) | — | F1 leitura |
| `consultar_prazo` (existente) | — | F1 leitura |
| `rastrear_entrega` (existente) | `track_shipments` | F1 leitura |
| `otimizar_entrega` | `optimize_delivery` | F1 análise |
| `organizar_envio` | `arrange_shipping` | F2 escrita (HITL) |
| `coordenar_operacoes` | `coordinate_operations` | F2 escrita (HITL) |
| `gerenciar_manuseio_especial` | `manage_specialist_handling` | F2 escrita (HITL) |
| `processar_devolucoes` | `process_returns` | F2 escrita (HITL) |
| `gerenciar_disrupcoes` | `manage_disruption` | F2 escrita (HITL) |

### Fornecedores

| Tool | Origem | F1 / F2 |
| --- | --- | --- |
| `listar_fornecedores` (existente) | — | F1 leitura |
| `consultar_fornecedor` (existente) | — | F1 leitura |
| `avaliar_desempenho` (existente) | `evaluate_suppliers` | F1 leitura |
| `tratar_conformidade` | `handle_compliance` | F1 análise (checagem) · F2 ação (regularização) |

### Reconciliação com a proposta anterior (AD-009)

As 4 tools provisórias de leitura da AD-009 ficam **substituídas** pelo inventário
acima, com suas capacidades incorporadas às tools nomeadas:

| Provisória (AD-009) | Ferramenta do catálogo |
| --- | --- |
| `listar_abaixo_minimo` | `prever_demanda` + `consultar_estoque` |
| `dias_de_cobertura` | `prever_demanda` |
| `comparar_fornecedores` | `avaliar_desempenho` |
| `listar_entregas_atrasadas` | `otimizar_entrega` + `rastrear_entrega` |

**Total F1**: 9 tools existentes (reapontadas ao repositório do tenant) + 6 novas
read-only/análise (`prever_demanda`, `otimizar_armazem`, `otimizar_custos`,
`otimizar_entrega`, `tratar_conformidade`, `enviar_resposta_logistica`) = **15**.

---

## Error Handling Strategy

| Error Scenario | Handling | User Impact |
| --- | --- | --- |
| Sem sessão / sessão expirada | Redireciona para login | Página de login |
| Acesso a recurso de outro tenant | 404 (não vaza existência) | "Não encontrado" |
| Arquivo de import inválido | Validação na entrada, erros por linha | Tela de status com motivos |
| LLM timeout/falha | Mensagem de degradação + auditoria | "Não consegui responder agora" |
| Quota de LLM excedida | Bloqueio com aviso | Aviso de limite do plano |
| Dado insuficiente para recomendar | Resposta de insuficiência | Orientação do que importar |

---

## Tech Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| Framework backend | FastAPI | Async, tipagem, casa com o core Python/LangGraph |
| UI | Jinja2 + HTMX + SSE | Menos peças para dev solo; streaming sem SPA |
| Tenancy | Postgres único + `tenant_id` | Simples, padrão de mercado; guardas na app + RLS opcional |
| Banco | PostgreSQL | JSONB para import, concorrência e escala SaaS |
| Auth | FastAPI Users (self-hosted) | Registro/login/convites em Python, sem vendor |
| Reuso do copiloto | Envelopar o grafo atual | Reaproveita 99% de cobertura e o desenho supervisor+especialistas |
| Persistência de dados da tools | Repositórios por tenant | Substitui o mock sem mudar prompts/assinaturas |

---

## Open Questions

1. Política de upsert na importação (SKU/fornecedor duplicados): substituir ou erro?
2. Formato exato do golden set (JSON/YAML? campos de fonte esperada?).
3. RLS no Postgres além das guardas na aplicação — ou apenas app-level no MVP?
4. Streaming: token a token do LLM ou a resposta final por SSE? (afeta p95 percebida)
