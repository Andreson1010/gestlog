# gestlog

**Vision:** Copiloto de decisão logística que recomenda e explica, em português,
sem executar ações nos sistemas do cliente.
**For:** Transportadoras e operadores logísticos de pequeno e médio porte (PMEs),
sem TI próprio, que hoje operam em planilha.
**Solves:** Decisões logísticas (reposição, fornecedor, frete, atrasos) ficam
lentas porque os dados estão dispersos em planilhas e sistemas desconectados.

## Goals

- Reduzir o tempo médio até a decisão logística de forma mensurável em uso real.
- Atingir **≥ 60% de recomendações aceitas** e alta acurácia em golden set.
- Melhorar indicadores operacionais (ruptura de estoque e entregas atrasadas).

## Tech Stack

**Core:**

- Framework: LangGraph + LangChain (langchain-core, langchain-openai)
- Language: Python >= 3.11
- Interface/API: aplicação web com chat (a definir no design da F1) + API FastAPI

**Key dependencies:** `pydantic` / `pydantic-settings`, endpoint LLM compatível
com OpenAI; qualidade com pytest + coverage, black e ruff.

## Scope

**v1 includes:**

- App web autenticado por **conta por empresa** (tenant) + login.
- **4 domínios read-only**: reposição de estoque, seleção de fornecedor,
  custo/prazo de frete, priorização de atrasos.
- **Importação** de dados (CSV/planilha) com validação.
- **Recomendação explicada** com fonte + aceitar/descartar.
- **LGPD**: redação de PII antes do LLM, retenção configurável, sem treino em
  dados do cliente.
- **LLM hospedado** pela plataforma, com medição de uso por tenant.

**Explicitly out of scope:**

- Execução de ações / escrita nos sistemas de origem (F2/HITL).
- Integrações de API em tempo real (F3).
- SSO corporativo, billing/planos, app mobile (F5).
- Alertas proativos / automação em background (F4).
- BYO-LLM / on-prem / multi-idioma (F5).
- Domínio de cadastros incompletos (F2).

## Constraints

- Timeline: **sem datas** — roadmap por fases e critérios de saída.
- Technical: **evoluir** o núcleo LangGraph atual, não recomeçar; sem novas
  dependências sem justificativa.
- Resources: **dev solo**; NFR modesto no MVP (~dezenas de tenants, p95 < 15s,
  disponibilidade best-effort).
