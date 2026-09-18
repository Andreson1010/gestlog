# ADR: t32-dashboard-kpis

## 1. Contexto & Objetivo

A F1 chegou ao fim com os fluxos de adoção (onboarding, importação e chat) e de
aceitação (recomendação e feedback) já persistidos, mas o gestor ainda não tinha
onde enxergar isso de forma agregada. O critério **KPI-01** é literal: *"WHEN o
gestor abre o dashboard THEN o sistema SHALL exibir os KPIs do tenant do
período"*, e a tarefa pede uma tela com **adoção, aceitação e cobertura de
dados** por tenant e período.

O obstáculo não era montar HTML, e sim **definir o que cada número significa** e
calculá-los sem furar o isolamento entre empresas. Três famílias de dados
convivem: conversas e mensagens (atividade), recomendações e decisões (funil,
este último *append-only*) e catálogos importados (estoque, fornecedores,
transporte). Cada uma tem uma noção própria de tempo, e o dashboard precisa
combiná-las em um único recorte sem que uma regra de negócio da T22 (última
decisão vence) se perca. O objetivo desta entrega foi, portanto, uma tela enxuta
apoiada em uma agregação **confinada ao repositório** e determinística.

## 2. Decisões de Arquitetura

**1. Agregação no repositório, SQL confinado à camada `libs`**

Todo o cálculo vive em `KpiRepository` (`src/gestlog/repositories/kpis.py`) e é
exposto como um único `ResumoKpis`, um `dataclass(frozen=True)` com contadores e
três propriedades derivadas (`decisoes`, `taxa_aceitacao`, `cobertura_dados`). A
rota `GET /kpis` não conhece SQL: recebe o `Membership` da sessão, chama
`resumo(empresa_id, desde, ate)` e entrega o objeto ao template. A justificativa
é a fronteira declarada no `AGENTS.md` — *"`db/` + `repositories/` são a única
porta de acesso ao banco"* — e o efeito prático é que a regra de agregação é
testável em integração com SQLite, sem subir a aplicação, e reutilizável por
qualquer consumidor futuro (exportação, API) sem duplicar consultas.

**2. Três métricas, três perguntas de negócio distintas**

O `ResumoKpis` separa o que o gestor realmente quer saber. **Adoção** é medida
por `conversas` (quantas conversas começaram no período) e `perguntas` (mensagens
de papel `user` dessas conversas), respondendo "o time está usando o copiloto?".
**Aceitação** é medida por `recomendacoes` e pelas decisões vigentes `aceitas` e
`descartadas`, com `taxa_aceitacao = aceitas / (aceitas + descartadas)`
deliberadamente sobre as **decididas**, e não sobre o total de recomendações:
assim uma recomendação ainda não avaliada não penaliza o indicador, e o `0.0`
sem decisões evita divisão por zero e comunica "sem base de comparação".
**Cobertura** é a soma de itens de estoque, fornecedores e registros de
transporte, respondendo "quanto dado o tenant já carregou para o copiloto
trabalhar". Manter as três separadas evita o erro clássico de misturar uso,
qualidade da recomendação e maturidade do dado em um único painel opaco.

**3. Período por data, com limites UTC inclusivos**

A tela recebe `desde` e `ate` como `date` (não `datetime`), porque o gestor pensa
em dias. A conversão para o intervalo fechado do dia acontece na borda web:
`_inicio` usa `datetime.combine(valor, time.min, tzinfo=UTC)` e `_fim` usa
`time.max` com o mesmo fuso, e o repositório aplica `>=`/`<=`. O recorte é
**inclusivo** nas duas pontas — o teste `test_pagina_kpis_filtra_periodo` confirma
que um registro no último dia entra no resultado. Fixar UTC na fronteira evita
depender do fuso do processo e mantém o mesmo resultado entre ambientes; a
conversão para o fuso do tenant é uma decisão de produto que só se justifica
quando houver tenants multi-fuso.

**4. Aceitação reutiliza a semântica da T22: "última decisão vence"**

O `Feedback` é *append-only* (cada clique grava uma linha, preservando a trilha
de auditoria), então contar linhas inflaria o KPI a cada troca de decisão. A
T23 já havia fixado a regra em `FeedbackRepository.latest_by_conversation`
(*"a última iteração de cada recomendação é a que fica"*), e a T32 a reaproveita
conceitualmente: `_decisoes_vigentes` percorre `Feedback` na ordem
`(created_at, id)` e sobrescreve um dicionário `{recommendation_id: decisao}`,
de modo que aceitar e depois descartar conta **uma** decisão — o descarte. A
diferença de implementação em relação à T23 é o escopo: `latest_by_conversation`
resolve *uma* conversa e seria chamado N vezes para o dashboard, enquanto aqui a
mesma redução é feita em **uma consulta** para todas as conversas do tenant no
período. A integridade do contrato é a mesma; a forma foi adaptada ao volume.

**5. Isolamento por empresa derivado da sessão, nunca do cliente**

O `empresa_id` vem do `Membership` resolvido por `exigir_papel`, não de
parâmetro de URL ou formulário. `_ids_conversas` filtra
`Conversation.empresa_id == empresa_id`; `perguntas` e `recomendacoes` operam
sobre esses ids; a cobertura conta `StockItem`/`Supplier`/`TransportRecord` por
`empresa_id`. Como `Message` e `Feedback` não carregam `empresa_id` (são
alcançados por `conversation_id`/`recommendation_id`), o recorte de conversas é
o que garante que nenhum dado de outro tenant entre na agregação. O teste
`test_kpi_repository_agrega_e_isola` semeia duas empresas com dados sobrepostos e
prova que os números não vazam.

**6. Guard `admin`/`gestor` com 401 e 403 distintos**

A rota depende de `exigir_papel("admin", "gestor")`, que por sua vez depende de
`get_current_membership` → `current_active_user`. Sem sessão a cadeia devolve
**401** (não autenticado); autenticado como `operador` devolve **403** (sem
permissão). A distinção é testada (`test_kpis_sem_sessao_retorna_401`,
`test_kpis_operador_recebe_403`) e é intencional: o operador não deve ver
indicadores de gestão, mas precisa saber que o problema é permissão e não falta
de login.

**7. Cobertura é snapshot, não recorte de período**

`itens_estoque`, `fornecedores` e `registros_transporte` são contados **sem**
`created_at`, porque os catálogos representam a última versão importada e não
têm histórico de versões. Isso é uma escolha explícita e agora documentada nos
docstrings de `cobertura_dados` e `resumo`: a pergunta é "quanto dado existe
agora", não "quanto entrou no período". As demais métricas respeitam o período.
Essa assimetria é visível na tela (o rótulo é o total corrente) e evita prometer
uma série temporal que o schema atual não sustenta.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **Redução em memória, não `ROW_NUMBER()` no banco:** `_decisoes_vigentes` traz
  as linhas de decisão e reduz em Python, em vez de uma janela analítica
  portável entre SQLite e Postgres. No volume da F1 o custo é irrelevante e a
  consulta fica legível; se o volume crescer, o índice em
  `feedback.recommendation_id` e uma janela SQL são a evolução natural — a
  própria ADR da T23 já apontava esse join/índice como próximo passo.
* **Recorte pelo início da conversa:** as métricas de conversa usam
  `Conversation.created_at`, não o `created_at` de cada mensagem/recomendação.
  É coerente com a unidade de adoção ("conversas do período") e mantém
  `decisoes <= recomendacoes`, mas significa que uma conversa longa que
  atravessa a fronteira conta inteira no período em que começou. Aceitável para
  o painel gerencial do MVP.
* **Sem token anti-CSRF novo:** a rota de KPIs é `GET` somente-leitura; não há
  escrita nem alteração de estado nesta task. O hardening de CSRF dos formulários
  continua no escopo mais amplo do épico, como registrado na T23.
* **Desempate por UUID em empates de timestamp (limitação documentada):**
  `_decisoes_vigentes` ordena por `(Feedback.created_at, Feedback.id)`. Como
  `Feedback.id` é um UUID4 **aleatório**, duas decisões para a **mesma**
  recomendação gravadas no **mesmo** timestamp têm ordem de desempate não
  determinística — o mesmo padrão já existente em
  `FeedbackRepository.latest_by_conversation` (T20/T23). É aceitável documentar
  como limitação: cliques reais de aceitar/descartar são separados por muito mais
  que a resolução do relógio (~microssegundos), e o histórico append-only
  preserva as duas linhas. A correção definitiva exigiria uma coluna monotônica
  de sequência/inserção (schema change), desproporcional para o MVP; fica
  registrada para quando auditoria exigir ordem à prova de empate.

## 4. O que vem a seguir (Roadmap Imediato)

* **T33 (aceitação P1 ponta a ponta):** o teste final percorre onboarding →
  importação → chat → recomendação → feedback; o dashboard da T32 será o ponto
  de leitura que comprova KPI-01 no fluxo real.
* **Exportação/relatório do dashboard — melhoria de produto:** um próximo passo
  natural é oferecer o recorte de período em CSV. Como toda a agregação já está
  isolada em `KpiRepository`, a mudança é uma rota nova sobre o mesmo
  `ResumoKpis`, sem tocar em SQL.
* **Fuso horário do tenant — limitação documentada:** hoje o período é UTC. Se o
  produto passar a operar multi-fuso, `_inicio`/`_fim` precisarão converter a
  partir do fuso do tenant, e a decisão de qual fuso usar deve vir do cadastro da
  empresa, não do processo.
* **Série temporal de cobertura — limitação documentada:** como cobertura é
  snapshot, não há como ver "quantos itens entraram em junho". Isso exige
  histórico de versões de catálogo (ou derivar do `ImportJob`), uma task própria.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio e privacidade:** o `empresa_id` é sempre resolvido da
  sessão via `exigir_papel`/`get_current_membership`, nunca do cliente; a
  subconsulta de conversas fecha o escopo, e nenhuma métrica agrega fora dela. O
  teste de isolamento confirma que dados de outra empresa não aparecem. A tela
  não chama LLM, não expõe PII e não escreve estado — é leitura autenticada.
* **Cobertura e testes automatizados:** `tests/web/test_kpis.py` concentra 3
  testes de repositório (agregação/isolamento, período, última decisão vence) +
  o regressivo `test_kpi_repository_decisao_respeita_periodo_da_conversa` +
  4 de integração HTTP (401 sem sessão, 403 operador, render com valores, filtro
  de período). Execução focada `tests/web tests/test_repositories.py`:
  **57 passed**. O gate completo anterior à revisão estava em **227 passed**,
  cobertura **98,26%**.
* **Padrões de qualidade:** `uv run python -m black --check src/ tests/ evals/` →
  96 arquivos inalterados; `uv run python -m ruff check src/ tests/ evals/` →
  All checks passed. Docstrings e nomes em português, `from __future__ import
  annotations` presente em todos os módulos, sem comentários fora de docstring,
  sem `print`, funções bem abaixo de 50 linhas e SQL restrito a
  `repositories/`.

## Achados corrigidos no self-review

* **Recorte de período inconsistente nas decisões (média):** `_decisoes_vigentes`
  filtrava `Recommendation.created_at` pelo período, enquanto `perguntas` e
  `recomendacoes` já usavam o recorte das **conversas** do período. Numa fronteira
  exata (conversa começada antes de `desde` com recomendação gerada depois, ou o
  inverso no fim), uma decisão podia ser contada sem a recomendação correspondente
  — `aceitas` podia exceder `recomendacoes`, quebrando a leitura do funil. A
  consulta passou a escopar por `Recommendation.conversation_id.in_(ids)`, o mesmo
  conjunto dos demais KPIs, e o invariante `decisoes <= recomendacoes` está
  coberto pelo regressivo `test_kpi_repository_decisao_respeita_periodo_da_conversa`
  (que falharia na implementação anterior).
* **Cobertura snapshot não estava explícita (baixa):** `cobertura_dados` e
  `resumo` ganharam docstring deixando claro que o total de catálogo é um retrato
  do estado atual, sem recorte de período — a assimetria em relação às métricas
  temporalmente recortadas agora é intencional e documentada.
* **Nome enganoso do guard (baixa):** o parâmetro local `gestor` foi renomeado
  para `vinculo` em `web/kpis.py`, já que o guard aceita `admin` **ou** `gestor`;
  o nome anterior sugeria uma restrição de papel que não existia.
* **Sem achados** de lint, formatação, tipagem, segredo hardcoded, vazamento entre
  empresas, injeção de SQL (consultas parametrizadas) ou uso de `print`.
* **Limitação aceita, não bloqueante:** o desempate por `Feedback.id` (UUID
  aleatório) em empates de timestamp permanece, alinhado ao padrão já aceito em
  `latest_by_conversation` (T20/T23); ver a seção de trade-offs para a
  justificativa e o caminho de correção futura.
