# Roadmap

**Current Milestone:** M1 — MVP (copiloto read-only)
**Status:** Planning

---

## M1 — MVP: copiloto read-only

**Goal:** PME-cliente importa seus dados e o operador recebe recomendações
explicadas nos 4 domínios, com aceitação/descarte medidos.
**Target (critérios de saída):** conta por empresa funcionando; importação de
CSV/planilha; 4 domínios respondendo; PII redigida antes do LLM; KPIs coletados.

### Features

**Contas e tenancy** - PLANNED

- Criar/gerenciar conta de empresa e convidar usuários
- Login e autorização por tenant
- Papéis: admin da conta e operador
- Isolamento de dados por `tenant_id`

**Ingestão de dados** - PLANNED

- Importar estoque, transporte e fornecedores (CSV/planilha)
- Validação e normalização na entrada; erros por linha
- Status/histórico de importação

**Copiloto (4 domínios)** - PLANNED

- Chat com roteamento supervisor (evolui o grafo atual)
- Reposição de estoque, seleção de fornecedor, custo/prazo de frete,
  priorização de atrasos
- Recomendação + justificativa + fonte; aviso de dado insuficiente
- Aceitar/descartar e histórico por usuário/tenant

**Qualidade e custo** - PLANNED

- Golden set por domínio (avaliação humana)
- Quota de LLM por tenant e medição de uso
- Logs/auditoria por tenant

---

## M2 — HITL: escrita com aprovação

**Goal:** o copiloto deixa de ser só read-only e passa a **corrigir/completar
cadastros incompletos** (e documentos) com aprovação humana.
**Target:** toda escrita passa por aprovação; trilha de auditoria por ação.

### Features

**Cadastros incompletos** - PLANNED

- Listar registros com campos faltantes por tenant
- Sugerir valores de preenchimento
- Aprovar → aplicar correção (HITL); registrar quem aprovou

**Fluxo de aprovação** - PLANNED

- Fila de recomendações acionáveis
- Aprovar/rejeitar com justificativa
- Auditoria completa das escritas

---

## M3 — Integrações de API

**Goal:** dados em tempo real por tenant.
**Target:** conectar ao menos um TMS/ERP/WMS por credenciais do cliente.

### Features

**Conectores por tenant** - PLANNED

- Credenciais por tenant e agendamento de sincronização
- Substituir/complementar a importação por arquivo
- Monitoramento de falhas de sincronização

---

## M4 — Proativo: alertas

**Goal:** o gestlog avisa antes do problema, sem o usuário perguntar.
**Target:** notificações de estoque baixo, atraso e fornecedor degradando.

### Features

**Monitoramento e alertas** - PLANNED

- Regras por domínio e limiares
- Notificações (in-app/e-mail)
- Supressão de ruído e preferências do usuário

---

## M5 — Enterprise

**Goal:** atender clientes maiores e opções de implantação.
**Target:** SSO, billing/planos, mobile, BYO-LLM/on-prem, multi-idioma.

### Features

**Escala e opções** - PLANNED

- SSO corporativo (SAML/OIDC)
- Billing/planos
- App mobile
- BYO-LLM / on-prem
- Multi-idioma

---

## Future Considerations

- Novos domínios além dos 4 do MVP (contratos, devoluções, inventário).
- Benchmarking entre tenants (anonimizado) para recomendações melhores.
- Marketplace de conectores mantidos por terceiros.
