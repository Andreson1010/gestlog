# Relatórios operacionais por domínio — Story

**Path:** docs/specs/features/relatorios-operacionais/story.md
**TLC scope:** complex
**Based on:** Dashboard /kpis (AD-028) como padrão de referência; feature_request "Relatórios operacionais por domínio"
**Status:** Aprovada (Checkpoint 1, 2026-09-28)

---

## Problem Statement

Hoje o gestor de uma PME de logística só enxerga indicadores agregados no dashboard /kpis (AD-028), que mostra números de adoção, aceitação e um retrato de cobertura de dados. Não existe uma visão tabular por domínio operacional (estoque, transporte, fornecedores), recortada por período, nem forma de levar esses dados para fora do produto. Os catálogos atuais (StockItem, Supplier, TransportRecord) também não têm timestamp, o que impede qualquer recorte de/até real — o /kpis trata cobertura como snapshot. Esta feature entrega relatórios tabulares por domínio, com período de/até de fato e exportação CSV, sem gráficos e sem agregação monetária.

## Goals

- [ ] O gestor/admin vê, por domínio (estoque, transporte, fornecedores), tabelas operacionais do próprio tenant.
- [ ] O recorte de período (de/até) é real, sustentado por timestamp nos catálogos (migração de schema).
- [ ] Cada domínio exporta a tabela visível em CSV, respeitando o mesmo recorte de tenant e período.
- [ ] O acesso é restrito a admin/gestor; o isolamento por tenant é garantido pelo Membership da sessão.

## Out of Scope

| Item | Motivo |
| --- | --- |
| Gráficos e visualizações | v1 é só tabelas + CSV (decisão do usuário) |
| Agregação monetária / custo | Não existe campo de custo persistido |
| Exportação em PDF ou XLSX | v1 exporta apenas CSV |
| Agendamento / envio recorrente por e-mail | Fora do escopo desta história |
| Relatório consolidado de múltiplas empresas (cross-tenant) | O tenant é sempre o do Membership; consolidação multiempresa fica para depois |
| Seleção de empresa ativa | MVP assume um vínculo por usuário (mesmo padrão de /kpis) |
| Filtros adicionais por local/categoria/status dentro do domínio | v1 recorta apenas por empresa e período |
| Alteração do dashboard /kpis existente | Esta história adiciona rotas novas; não mexe no /kpis |
| Retenção/expurgo dos arquivos CSV gerados | Não há persistência das exportações |

## User Stories

### P1: Relatório de estoque por período

**User Story**: Como gestor de logística, quero ver uma tabela do estoque da minha empresa recortada por período, com itens abaixo do mínimo, excedentes e contagens por local e categoria, para agir sobre o que está fora da faixa ideal.

**Why P1**: estoque é o domínio operacional mais crítico e o primeiro relatório pedido.

**Acceptance Criteria**:
1. WHEN o gestor acessa a rota do domínio estoque THEN o sistema SHALL renderizar uma página com tabelas do domínio, apenas com registros da empresa da sessão.
2. WHEN há itens com quantidade abaixo do mínimo THEN o sistema SHALL listá-los com sku, nome, quantidade, mínimo e local.
3. WHEN há itens classificados como excedentes THEN o sistema SHALL listá-los conforme o critério de excedente definido (limiar em aberto — Open Question 2).
4. WHEN o relatório de estoque é exibido THEN o sistema SHALL mostrar a contagem de itens por local.
5. WHEN o relatório de estoque é exibido THEN o sistema SHALL mostrar a contagem de itens por categoria (dependente de a migração incluir categoria no estoque — Open Question 1).
6. WHEN o período é informado THEN o sistema SHALL aplicar o recorte de/até inclusivo ao conjunto considerado (Open Question 6).

**Independent Test**: criar duas empresas com itens distintos e itens abaixo/acima do mínimo; confirmar os itens listados, a contagem por local/categoria e o recorte de período para a empresa correta.

---

### P1: Relatório de transporte por período

**User Story**: Como gestor de logística, quero ver uma tabela do transporte da minha empresa recortada por período, com contagem por status, atrasos e peso (kg) por rota, para acompanhar a operação logística no período.

**Why P1**: transporte concentra o acompanhamento de prazos e volumes da operação.

**Acceptance Criteria**:
1. WHEN o gestor acessa a rota do domínio transporte THEN o sistema SHALL renderizar uma página com tabelas do domínio, apenas com registros da empresa da sessão.
2. WHEN o relatório de transporte é exibido THEN o sistema SHALL mostrar a contagem de registros por status.
3. WHEN o relatório de transporte é exibido THEN o sistema SHALL mostrar o total de peso (kg) agrupado por rota, segundo a definição de rota (Open Question 4).
4. WHEN o relatório de transporte é exibido THEN o sistema SHALL mostrar a contagem de atrasos, segundo a definição de atraso (Open Question 3).
5. WHEN o período é informado THEN o sistema SHALL aplicar o recorte de/até inclusivo ao conjunto considerado (Open Question 6).

**Independent Test**: criar registros com status, rotas e pesos variados; confirmar as contagens por status, a soma de peso por rota e o recorte de período.

---

### P1: Relatório de fornecedores por período

**User Story**: Como gestor de logística, quero ver uma tabela de fornecedores da minha empresa recortada por período, com conformidade (ativo, avaliação, prazo) e contagem por categoria, para avaliar a base de fornecedores no período.

**Why P1**: fornecedores completam os três domínios operacionais pedidos.

**Acceptance Criteria**:
1. WHEN o gestor acessa a rota do domínio fornecedores THEN o sistema SHALL renderizar uma página com tabelas do domínio, apenas com registros da empresa da sessão.
2. WHEN o relatório de fornecedores é exibido THEN o sistema SHALL mostrar a distribuição de fornecedores ativos e inativos.
3. WHEN o relatório de fornecedores é exibido THEN o sistema SHALL mostrar os indicadores de avaliação e prazo_dias dos fornecedores (Open Question 5).
4. WHEN o relatório de fornecedores é exibido THEN o sistema SHALL mostrar a contagem de fornecedores por categoria.
5. WHEN o período é informado THEN o sistema SHALL aplicar o recorte de/até inclusivo ao conjunto considerado (Open Question 6).

**Independent Test**: criar fornecedores ativos/inativos, com categorias, avaliações e prazos distintos; confirmar as contagens e os indicadores para o período.

---

### P1: Recorte por empresa e período

**User Story**: Como gestor, quero que todos os relatórios sejam sempre da minha empresa e do período que eu escolhi, para não misturar dados de outras empresas nem perder o recorte ao navegar.

**Why P1**: tenancy e período são a base de confiança de qualquer relatório.

**Acceptance Criteria**:
1. WHEN qualquer relatório ou exportação é solicitado THEN o sistema SHALL derivar a empresa do Membership da sessão, ignorando qualquer empresa_id vindo do cliente.
2. WHEN existe um parâmetro de empresa no pedido apontando para outra empresa THEN o sistema SHALL ignorá-lo e nunca expor registros de outra empresa.
3. WHEN nenhum de/até é informado THEN o sistema SHALL considerar todo o histórico disponível da empresa.
4. WHEN de e/ou até são informados THEN o sistema SHALL incluir registros cujo timestamp esteja no intervalo UTC inclusivo (de 00:00:00.000000 a 23:59:59.999999).
5. WHEN de é igual a até THEN o sistema SHALL incluir os registros daquele dia.
6. WHEN a página é re-renderizada com um filtro aplicado THEN o sistema SHALL manter os valores de de/até nos campos do formulário.

**Independent Test**: com dois tenants, confirmar que o tenant A nunca vê dados de B mesmo enviando empresa_id de B; testar limites de período inclusivos e o caso de == até.

---

### P1: Guarda de acesso (401/403)

**User Story**: Como admin da conta, quero que os relatórios sejam acessíveis só a admin/gestor, para proteger dados operacionais da empresa.

**Why P1**: é requisito de segurança, igual ao /kpis.

**Acceptance Criteria**:
1. WHEN um visitante sem sessão válida acessa uma rota de relatório ou de exportação THEN o sistema SHALL responder 401.
2. WHEN um usuário autenticado com papel operador acessa uma rota de relatório ou de exportação THEN o sistema SHALL responder 403.
3. WHEN um usuário com papel admin ou gestor acessa as três rotas de domínio THEN o sistema SHALL responder 200.

**Independent Test**: chamar cada rota sem sessão (401), como operador (403) e como admin/gestor (200).

---

### P1: Exportação CSV por domínio

**User Story**: Como gestor, quero exportar a tabela do domínio em CSV com o mesmo recorte da tela, para analisar os dados em uma planilha.

**Why P1**: a exportação é o valor prático do relatório; sem ela o dado fica preso na interface.

**Acceptance Criteria**:
1. WHEN o gestor solicita a exportação de um domínio THEN o sistema SHALL devolver um arquivo CSV com cabeçalho e linhas correspondentes à tabela exibida, com o mesmo recorte de empresa e período.
2. WHEN o CSV é servido THEN a resposta SHALL ter cabeçalho de anexo (Content-Disposition attachment) com um nome de arquivo contendo o domínio e o período.
3. WHEN o CSV é servido THEN o conteúdo SHALL estar em UTF-8.
4. WHEN um campo contém o separador, aspas ou quebra de linha THEN o valor SHALL ser escapado/citado conforme a RFC 4180, permanecendo parseável.
5. WHEN um campo começa por um caractere que planilhas interpretam como fórmula (=, +, -, @) THEN o valor SHALL ser neutralizado para não ser executado ao abrir o arquivo (CSV injection).
6. WHEN a exportação é solicitada sem sessão THEN o sistema SHALL responder 401; como operador, 403.
7. WHEN a exportação é solicitada THEN o sistema SHALL nunca incluir registros de outra empresa.
8. WHEN a empresa do recorte não tem registros THEN o sistema SHALL devolver um CSV apenas com o cabeçalho, sem erro.
9. WHEN a exportação é gerada a partir do mesmo filtro da tela THEN as linhas exportadas SHALL corresponder exatamente ao que a tela mostra.

**Independent Test**: exportar cada domínio com e sem período; abrir o CSV e conferir cabeçalho, linhas, escape de campos especiais e nome do arquivo; repetir sem sessão e como operador.

---

## Edge Cases

- WHEN apenas de é informado (sem até) THEN o sistema SHALL aplicar só o limite inferior, inclusive.
- WHEN apenas até é informado (sem de) THEN o sistema SHALL aplicar só o limite superior, inclusive.
- WHEN de é posterior a até THEN o comportamento SHALL seguir a decisão pendente (Open Question 9), resultando em conjunto vazio ou erro de validação coerente.
- WHEN a empresa não tem nenhum registro em nenhum domínio THEN o sistema SHALL exibir estado vazio claro, sem erro, e exportar CSV apenas com cabeçalho.
- WHEN um campo de texto (status, local, categoria, origem, destino) contém vírgula, ponto e vírgula, aspas ou quebra de linha THEN a exportação SHALL permanecer parseável (RFC 4180).
- WHEN um campo de texto começa por =, +, -, @ ou por caractere de controle THEN a exportação SHALL neutralizar a fórmula.
- WHEN um campo de texto é vazio (string padrão dos catálogos) THEN o sistema SHALL tratá-lo como valor real vazio, não como erro.
- WHEN peso_kg é zero THEN a soma da rota SHALL contabilizar zero sem omitir a rota indevidamente.
- WHEN avaliacao é 0.0 ou prazo_dias é 0 THEN o sistema SHALL exibi-los como valores reais, não como ausentes.
- WHEN o mínimo do item é zero THEN a classificação abaixo do mínimo/excedente SHALL seguir a regra escolhida (Open Question 2), sem divisão por zero.
- WHEN um parâmetro de data é inválido (ex.: de=abc) THEN o sistema SHALL responder erro de validação (422) do framework.
- WHEN o volume de registros é grande THEN as agregações SHALL ser feitas em uma consulta agrupada (GROUP BY), sem N+1.
- WHEN um registro é importado durante a geração do relatório THEN o resultado SHALL ser consistente com o instante da consulta, sem estado parcial.
- WHEN o dia UTC difere do fuso local do usuário THEN o recorte SHALL seguir a regra UTC inclusiva (consistente com /kpis).

## Open Questions

1. **Categoria no estoque** — StockItem não possui coluna categoria (e a ingestão de estoque não a lê), mas a decisão de métricas pede contagem por categoria no estoque. A migração também adiciona categoria ao estoque, ou o critério de categoria vale só para fornecedores? — matters because: sem a coluna, o critério 5 de estoque é inatendível e a migração/ingestão mudam.
2. **Critério de excedente no estoque** — usar a convenção existente quantidade > mínimo * 2 (tools/inventory.py) ou outro limiar (percentual, valor fixo)? — matters because: muda o conjunto listado como excedente.
3. **Definição de atraso no transporte** — TransportRecord não tem data de entrega nem prazo; como o atraso é determinado (campo novo, status específico, comparação com data)? — matters because: pode exigir novo campo/dado e muda o critério.
4. **Definição de rota no transporte** — rota é o par origem-destino, apenas origem ou apenas destino? — matters because: muda o agrupamento e a soma de peso.
5. **Conformidade de fornecedores** — é apenas a distribuição de ativo/avaliação/prazo, ou um indicador composto (ex.: ativos com avaliação acima de X e prazo abaixo de Y)? — matters because: define a métrica e sua testabilidade.
6. **Semântica do timestamp da migração** — created_at (data de criação/importação) ou atualizado_em? Um timestamp único representa o estado no período ou apenas o registro criado no período? — matters because: um catálogo atual com um único timestamp não reconstrói valores históricos (ex.: quantidade abaixo do mínimo no passado).
7. **Formato do CSV** — separador vírgula ou ponto e vírgula? usar BOM UTF-8 para o Excel pt-BR? — matters because: afeta a abertura em planilhas e os testes de formato.
8. **Nome do arquivo CSV** — qual o padrão exato (ex.: relatorio-estoque-2026-09-01_2026-09-30.csv)? — matters because: precisa ser verificável em teste.
9. **de maior que até** — retornar erro de validação (422/400) ou resultado vazio? — matters because: define UX e o teste do caso.
10. **Rota de exportação** — qual o caminho exato do export por domínio (ex.: /relatorios/{dominio}/exportar)? — matters because: precisa ser estável e testável.
11. **Cabeçalhos das tabelas e do CSV** — confirmar os rótulos em português de colunas e métricas (ex.: "Abaixo do mínimo", "Excedente", "Peso (kg)"). — matters because: os critérios da tabela e do CSV dependem dos rótulos.
12. **Empresa sem dados na exportação** — CSV só com cabeçalho (200) ou 204 sem corpo? — matters because: define o contrato da resposta.

---

## Decisões aprovadas (Checkpoint 1, 2026-09-28)

| Open Question | Decisão |
| --- | --- |
| Q1 — categoria no estoque | Migração adiciona coluna `categoria` ao `StockItem` **e** a ingestão passa a ler/gravar categoria. |
| Q2 — excedente | `quantidade > mínimo * 2` (convenção de `tools/inventory.py`); `mínimo = 0` nunca divide. |
| Q3 — atraso no transporte | Migração adiciona `previsao_entrega`; **atraso = entregue após a previsão**. |
| Q4 — rota | Par **origem → destino**. |
| Q5 — conformidade de fornecedores | Distribuição de `ativo` + indicadores `avaliacao` e `prazo_dias` (sem indicador composto). |
| Q6 — semântica do período | **Tabela de histórico por importação** (snapshot versionado a cada importação); o recorte de/até consulta o histórico, permitindo estado real no período. |
| Q7 — formato CSV | Separador `;`, UTF-8 **com BOM** (Excel pt-BR). |
| Q8 — nome do arquivo | `relatorio-{dominio}-{de}_{ate}.csv` (datas ausentes omitidas). |
| Q9 — de > até | Erro de validação **422**. |
| Q10 — rota de export | `GET /relatorios/{dominio}/exportar`. |
| Q11 — cabeçalhos | Rótulos em português (ex.: "Abaixo do mínimo", "Excedente", "Peso (kg)"). |
| Q12 — empresa sem dados | CSV apenas com cabeçalho, **HTTP 200**. |

> Consequência de escopo: Q1/Q3/Q6 exigem **migração Alembic** (categoria no estoque,
> `previsao_entrega` no transporte e tabela de histórico por importação) e ajuste na
> **ingestão** para popular categoria. O spec-writer deve detalhar schema, backfill e
> compatibilidade com os dados existentes.

**Esta história exige aprovação humana antes de iniciar spec/design/tasks.**