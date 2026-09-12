# F1 — MVP do gestlog (copiloto read-only) — Specification

**Path:** `docs/specs/features/f1-mvp/spec.md`
**TLC scope:** complex
**Based on story:** gestlog como SaaS multi-cliente: PME importa seus dados e o operador recebe recomendações explicadas nos 4 domínios.
**Status:** Awaiting human approval

---

## Problem Statement

PMEs de logística decidem (reposição, fornecedor, frete, atrasos) com dados
espalhados em planilhas e sistemas desconectados, perdendo tempo e padronização.
O MVP entrega um copiloto read-only, em português, que ingere os dados que a PME
já tem e recomenda decisões **explicadas**, sem tocar nos sistemas de origem.

## Goals

- [ ] Operador recebe recomendação explicada nos 4 domínios em uma sessão de chat.
- [ ] PME importa seus dados (CSV/planilha) e o operador já decide sobre eles.
- [ ] Isolamento por tenant e LGPD (PII redigida) desde o MVP.
- [ ] KPIs do produto coletados: aceitação, tempo até decidir, qualidade da IA.

## Out of Scope

| Feature | Reason |
| --- | --- |
| Escrita/execução de ações nos sistemas | F2 (HITL) — decisão de segurança |
| Integrações de API em tempo real (TMS/ERP/WMS) | F3 |
| Alertas proativos / background | F4 |
| SSO, billing, mobile, BYO-LLM/on-prem, i18n | F5 |
| Domínio de cadastros incompletos (correção) | F2 (valor está na escrita) |

---

## User Stories

### P1: Conta por empresa, login e isolamento ⭐ MVP

**User Story**: Como administrador de uma PME, quero criar a conta da minha
empresa, convidar meu time e ter os dados isolados dos outros clientes, para que
cada operador acesse só a nossa operação.

**Why P1**: Sem tenancy e auth não existe SaaS; tudo depende disso.

**Acceptance Criteria**:
1. WHEN um admin cria uma conta THEN o sistema SHALL criar um tenant e torná-lo
   proprietário.
2. WHEN um usuário faz login com credenciais válidas THEN o sistema SHALL obter
   uma sessão autenticada vinculada ao tenant.
3. WHEN um admin convida um usuário THEN o sistema SHALL permitir o acesso
   restrito àquele tenant com o papel definido.
4. WHEN qualquer consulta a dados é feita THEN o sistema SHALL restringi-la ao
   `tenant_id` da sessão.
5. WHEN request sem sessão válida acessa recurso protegido THEN o sistema SHALL
   retornar 401/redirecionar para login.
6. WHEN o usuário é de um tenant e tenta acessar recurso de outro THEN o sistema
   SHALL negar (404/403) sem vazar existência.

**Independent Test**: Criar 2 tenants, importar dados distintos, logar em cada um
e verificar que as consultas e o chat só enxergam os dados do próprio tenant.

---

### P1: Importação de dados ⭐ MVP

**User Story**: Como admin, quero importar estoque, transporte e fornecedores a
partir de CSV/planilha, para que o copiloto tenha dados reais para recomendar.

**Why P1**: Sem dados, o copiloto não tem o que recomendar.

**Acceptance Criteria**:
1. WHEN o admin envia um arquivo CSV/planilha de um tipo THEN o sistema SHALL
   validar as colunas esperadas e normalizar os valores.
2. WHEN uma linha tem erro THEN o sistema SHALL rejeitá-la e reportar o motivo e
   a linha, sem abortar as demais.
3. WHEN a importação conclui THEN o sistema SHALL registrar status, contagem de
   linhas aceitas/rejeitadas e timestamp, sempre por tenant.
4. WHEN o admin consulta o histórico THEN o sistema SHALL listar as importações
   do tenant com o resultado.
5. WHEN o arquivo é vazio ou de tipo desconhecido THEN o sistema SHALL falhar com
   mensagem clara e não alterar os dados.

**Independent Test**: Importar um arquivo válido + um com linhas inválidas e ver
o status com contagens corretas.

---

### P1: Chat com os 4 domínios ⭐ MVP

**User Story**: Como operador, quero perguntar em linguagem natural sobre
estoque, fornecedor, frete e atrasos, para receber uma resposta objetiva em
segundos.

**Why P1**: É o núcleo de valor — o copiloto.

**Acceptance Criteria**:
1. WHEN o operador envia uma pergunta THEN o sistema SHALL roteá-la ao domínio
   adequado (supervisor) e responder com os dados do tenant.
2. WHEN a pergunta envolve reposição, fornecedor, frete ou atraso THEN o sistema
   SHALL usar as ferramentas read-only do domínio correspondente.
3. WHEN falta um dado essencial THEN o sistema SHALL perguntar em vez de inventar.
4. WHEN a pergunta está fora do escopo THEN o sistema SHALL dizer que não cobre
   aquele assunto.
5. WHEN a resposta é gerada THEN o sistema SHALL transmiti-la em streaming ao
   usuário (SSE).

**Independent Test**: Fazer uma pergunta de cada domínio e uma fora do escopo,
com dados importados.

---

### P1: Recomendação explicada + aceite ⭐ MVP

**User Story**: Como operador, quero ver a recomendação, sua justificativa e a
fonte, e registrar se aceitei, para confiar na decisão e alimentar as métricas.

**Why P1**: "Explicada" é o diferencial e o aceite alimenta os KPIs.

**Acceptance Criteria**:
1. WHEN o sistema recomenda THEN SHALL apresentar recomendação + justificativa +
   a(s) fonte(s) do dado usado.
2. WHEN não há base suficiente para recomendar THEN o sistema SHALL informar a
   insuficiência, sem recomendação inventada.
3. WHEN o operador aceita ou descarta THEN o sistema SHALL registrar a decisão
   com usuário, tenant e timestamp.
4. WHEN a conversa avança THEN o sistema SHALL manter o histórico do usuário no
   tenant e recuperá-lo ao voltar.

**Independent Test**: Receber uma recomendação, aceitar, recarregar a página e
ver o histórico e o registro do aceite.

---

### P1: Privacidade, retenção e auditoria ⭐ MVP

**User Story**: Como admin, quero que dados pessoais não vazem para o provedor
de LLM e que haja trilha de auditoria, para cumprir LGPD.

**Why P1**: PII de clientes está no escopo e o LLM é de terceiros.

**Acceptance Criteria**:
1. WHEN texto com PII (nomes, endereços, telefones) vai ao LLM THEN o sistema
   SHALL redigir/minimizar a PII antes do envio.
2. WHEN o tenant define um período de retenção THEN o sistema SHALL respeitá-lo
   para conversas e dados armazenados.
3. WHEN ocorre uma interação relevante (pergunta, recomendação, aceite,
   importação) THEN o sistema SHALL registrar em auditoria por tenant.
4. WHEN dados são enviados ao provedor THEN SHALL ser sob DPA/zero-retention
   (sem uso para treino).

**Independent Test**: Enviar pergunta contendo PII e verificar no log de auditoria
que o texto enviado ao LLM não contém a PII.

---

### P1: Qualidade e custo ⭐ MVP

**User Story**: Como gestor, quero medir a qualidade das recomendações e o consumo
de LLM por tenant, para controlar custo e confiança.

**Why P1**: KPIs de qualidade e o custo da plataforma dependem disso.

**Acceptance Criteria**:
1. WHEN um golden set por domínio é executado THEN o sistema SHALL reportar
   acurácia e casos de alucinação/fonte incorreta.
2. WHEN um tenant chama o LLM THEN o sistema SHALL medir tokens/uso e atribuí-lo
   ao tenant.
3. WHEN o tenant atinge a quota THEN o sistema SHALL bloquear novas chamadas com
   mensagem clara, sem derrubar a sessão.

**Independent Test**: Rodar o golden set e ver o relatório; estourar a quota de um
tenant e ver o bloqueio.

---

### P2: Administração do tenant

**User Story**: Como admin, quero gerenciar usuários/papéis e ver o status das
importações, para operar a conta com autonomia.

**Acceptance Criteria**:
1. WHEN o admin altera o papel de um usuário THEN o sistema SHALL refletir as
   permissões na próxima requisição.
2. WHEN o admin remove um usuário THEN o sistema SHALL revogar seu acesso.

**Independent Test**: Trocar papel e validar permissões.

---

### P3: Dashboard de KPIs

**User Story**: Como gestor, quero ver adoção, aceitação e cobertura de dados,
para acompanhar o valor entregue.

**Acceptance Criteria**:
1. WHEN o gestor abre o dashboard THEN o sistema SHALL exibir os KPIs do tenant
   do período.

---

## Edge Cases

- WHEN a importação traz SKUs/fornecedores duplicados THEN o sistema SHALL aplicar
  a política de upsert definida no design e reportar.
- WHEN a pergunta cita dado inexistente no tenant THEN o sistema SHALL responder
  que não encontrou, sem alucinar.
- WHEN o LLM falha/timeout THEN o sistema SHALL degradar com mensagem clara e
  registrar o erro.
- WHEN o arquivo importado é grande THEN o sistema SHALL processar em lotes sem
  travar a UI.
- WHEN o tenant não tem nenhum dado importado THEN o sistema SHALL orientar a
  importar antes de recomendar.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| ACC-01 | P1: Conta/login/isolamento | Design | Pending |
| ACC-02 | P1: Conta/login/isolamento | Design | Pending |
| ACC-03 | P1: Conta/login/isolamento | Design | Pending |
| ACC-04 | P1: Conta/login/isolamento | Design | Pending |
| ING-01 | P1: Importação | Design | Pending |
| ING-02 | P1: Importação | Design | Pending |
| ING-03 | P1: Importação | Design | Pending |
| COP-01 | P1: Chat 4 domínios | Design | Pending |
| COP-02 | P1: Chat 4 domínios | Design | Pending |
| COP-03 | P1: Chat 4 domínios | Design | Pending |
| COP-04 | P1: Recomendação explicada | Design | Pending |
| COP-05 | P1: Recomendação explicada | Design | Pending |
| COP-06 | P1: Recomendação explicada | Design | Pending |
| SEC-01 | P1: Privacidade/auditoria | Design | Pending |
| SEC-02 | P1: Privacidade/auditoria | Design | Pending |
| SEC-03 | P1: Privacidade/auditoria | Design | Pending |
| QUA-01 | P1: Qualidade e custo | Design | Pending |
| QUA-02 | P1: Qualidade e custo | Design | Pending |
| ADM-01 | P2: Administração | - | Pending |
| KPI-01 | P3: Dashboard | - | Pending |

**Coverage:** 20 total, 0 mapped to tasks (tasks phase pending), 20 unmapped ⚠️

---

## Success Criteria

- [ ] Uma PME importa dados e o operador decide nos 4 domínios sem sair do chat.
- [ ] Nenhuma consulta cruza tenants (teste dedicado passa).
- [ ] Nenhuma PII sai para o LLM no caminho de teste.
- [ ] KPIs de aceitação e qualidade são coletados por tenant.
- [ ] p95 da recomendação < 15s no ambiente de referência.
