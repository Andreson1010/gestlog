# Relatórios operacionais por domínio — Technical Spec

**Path:** `docs/specs/features/relatorios-operacionais/spec.md`
**TLC scope:** complex
**Based on story:** gestor/admin vê relatórios tabulares (estoque, transporte, fornecedores) da própria empresa, recortados por período e exportáveis em CSV.
**Status:** Approved (Checkpoint 2, 2026-09-28)
**Fonte de requisitos:** `docs/specs/features/relatorios-operacionais/story.md` (aprovada no Checkpoint 1; decisões Q1–Q12 vinculantes).

---

## Problem Statement

O dashboard `/kpis` (AD-028) mostra indicadores agregados, mas não uma visão tabular por domínio operacional recortada por período, nem exportação. Os catálogos (`StockItem`, `Supplier`, `TransportRecord`) não têm timestamp e não reconstroem estado passado, o que impede um recorte de/até real. Esta feature adiciona relatórios tabulares por domínio, sustentados por uma tabela de histórico versionada por importação, com exportação CSV.

## Goals

- [ ] O gestor/admin acessa `/relatorios/{dominio}` para `estoque`, `transporte` e `fornecedores` e vê tabelas da própria empresa.
- [ ] O recorte de/até é real e inclusivo (UTC), sustentado por histórico versionado populado na importação e por backfill dos dados existentes.
- [ ] Cada domínio exporta em CSV (`GET /relatorios/{dominio}/exportar`) com o mesmo recorte de empresa e período.
- [ ] Acesso restrito a admin/gestor (401 sem sessão, 403 operador), com empresa sempre derivada do `Membership`.

## Out of Scope

| Feature | Reason |
| --- | --- |
| Gráficos e visualizações | v1 é só tabelas + CSV (decisão do usuário) |
| Agregação monetária / custo | Não existe campo de custo persistido |
| Exportação PDF/XLSX | v1 exporta apenas CSV |
| Agendamento / envio recorrente por e-mail | Fora do escopo da história |
| Relatório consolidado multiempresa (cross-tenant) | Tenant é sempre o do `Membership` |
| Seleção de empresa ativa | MVP assume um vínculo por usuário (padrão /kpis) |
| Filtros adicionais (local/categoria/status) | v1 recorta só por empresa e período |
| Alteração do dashboard `/kpis` | Esta história adiciona rotas novas |
| Retenção/expurgo dos CSVs gerados | Não há persistência das exportações |
| Biblioteca externa de CSV/gráficos | Usar `csv` da stdlib |

---

## User Stories

### P1: Relatório de estoque por período ⭐ MVP
**User Story**: Como gestor de logística, quero ver uma tabela do estoque da minha empresa recortada por período, com itens abaixo do mínimo, excedentes e contagens por local e categoria.
**Why P1**: estoque é o domínio operacional mais crítico.

**Acceptance Criteria**:
1. WHEN o gestor acessa `/relatorios/estoque` THEN o sistema SHALL renderizar a página só com registros da empresa da sessão.
2. WHEN há itens com `quantidade < mínimo` THEN o sistema SHALL listá-los com sku, nome, quantidade, mínimo e local.
3. WHEN há itens excedentes THEN o sistema SHALL classificá-los como `quantidade > mínimo * 2`, e nunca classificar quando `mínimo == 0`.
4. WHEN a página é exibida THEN o sistema SHALL mostrar a contagem de itens por local.
5. WHEN a página é exibida THEN o sistema SHALL mostrar a contagem de itens por categoria.
6. WHEN o período é informado THEN o sistema SHALL aplicar o recorte de/até inclusivo.

**Independent Test**: criar duas empresas com itens distintos (abaixo/acima do mínimo, locais e categorias) e confirmar listas, contagens e recorte.

---

### P1: Relatório de transporte por período ⭐ MVP
**User Story**: Como gestor de logística, quero ver uma tabela do transporte da minha empresa recortada por período, com contagem por status, atrasos e peso por rota.

**Acceptance Criteria**:
1. WHEN o gestor acessa `/relatorios/transporte` THEN o sistema SHALL renderizar a página só com registros da empresa da sessão.
2. WHEN a página é exibida THEN o sistema SHALL mostrar a contagem de registros por status.
3. WHEN a página é exibida THEN o sistema SHALL mostrar o total de peso (kg) agrupado por rota (`origem → destino`), incluindo rotas com peso zero.
4. WHEN a página é exibida THEN o sistema SHALL contar atrasos como `data_entrega > previsao_entrega` (ambos preenchidos).
5. WHEN o período é informado THEN o sistema SHALL aplicar o recorte de/até inclusivo.

**Independent Test**: criar registros com status, rotas, pesos, previsões e entregas variados; conferir as contagens, a soma por rota e o recorte.

---

### P1: Relatório de fornecedores por período ⭐ MVP
**User Story**: Como gestor de logística, quero ver uma tabela de fornecedores da minha empresa recortada por período, com conformidade (ativo, avaliação, prazo) e contagem por categoria.

**Acceptance Criteria**:
1. WHEN o gestor acessa `/relatorios/fornecedores` THEN o sistema SHALL renderizar a página só com registros da empresa da sessão.
2. WHEN a página é exibida THEN o sistema SHALL mostrar a distribuição de fornecedores ativos e inativos.
3. WHEN a página é exibida THEN o sistema SHALL mostrar os indicadores de avaliação e prazo_dias (médias), exibindo `0.0`/`0` como valores reais.
4. WHEN a página é exibida THEN o sistema SHALL mostrar a contagem de fornecedores por categoria.
5. WHEN o período é informado THEN o sistema SHALL aplicar o recorte de/até inclusivo.

**Independent Test**: criar fornecedores ativos/inativos com categorias, avaliações e prazos distintos; conferir contagens e indicadores.

---

### P1: Recorte por empresa e período ⭐ MVP
**User Story**: Como gestor, quero que todos os relatórios sejam sempre da minha empresa e do período escolhido.

**Acceptance Criteria**:
1. WHEN qualquer relatório ou exportação é solicitado THEN o sistema SHALL derivar a empresa do `Membership` da sessão, ignorando qualquer `empresa_id` do cliente.
2. WHEN um parâmetro de empresa no pedido aponta para outra empresa THEN o sistema SHALL ignorá-lo e nunca expor registros de outra empresa.
3. WHEN nenhum de/até é informado THEN o sistema SHALL considerar todo o histórico disponível da empresa.
4. WHEN de e/ou até são informados THEN o sistema SHALL incluir registros cujo `importado_em` esteja no intervalo UTC inclusivo (de 00:00:00.000000 a 23:59:59.999999).
5. WHEN `de == até` THEN o sistema SHALL incluir os registros daquele dia.
6. WHEN a página é re-renderizada com um filtro aplicado THEN o sistema SHALL manter os valores de de/até nos campos do formulário.

**Independent Test**: com dois tenants, confirmar isolamento mesmo enviando `empresa_id` alheio; testar limites inclusivos e `de == até`.

---

### P1: Guarda de acesso (401/403) ⭐ MVP
**User Story**: Como admin da conta, quero que os relatórios sejam acessíveis só a admin/gestor.

**Acceptance Criteria**:
1. WHEN um visitante sem sessão acessa uma rota de relatório ou de exportação THEN o sistema SHALL responder 401.
2. WHEN um usuário autenticado com papel `operador` acessa uma rota de relatório ou de exportação THEN o sistema SHALL responder 403.
3. WHEN um usuário `admin` ou `gestor` acessa as três rotas de domínio THEN o sistema SHALL responder 200.

**Independent Test**: chamar cada rota sem sessão (401), como operador (403) e como admin/gestor (200).

---

### P1: Exportação CSV por domínio ⭐ MVP
**User Story**: Como gestor, quero exportar a tabela do domínio em CSV com o mesmo recorte da tela.

**Acceptance Criteria**:
1. WHEN o gestor solicita a exportação de um domínio THEN o sistema SHALL devolver um CSV com cabeçalho e linhas correspondentes à tabela principal exibida, com o mesmo recorte de empresa e período.
2. WHEN o CSV é servido THEN a resposta SHALL ter `Content-Disposition: attachment` com nome `relatorio-{dominio}-{de}_{ate}.csv` (datas ausentes omitidas).
3. WHEN o CSV é servido THEN o conteúdo SHALL estar em UTF-8 com BOM (Excel pt-BR).
4. WHEN um campo contém `;`, aspas ou quebra de linha THEN o valor SHALL ser escapado/citado conforme RFC 4180, permanecendo parseável.
5. WHEN um campo de texto começa por `=`, `+`, `-`, `@` (ou tab/CR) THEN o valor SHALL ser neutralizado (prefixo `'`) para não ser executado como fórmula.
6. WHEN a exportação é solicitada sem sessão THEN 401; como operador, 403.
7. WHEN a exportação é solicitada THEN o sistema SHALL nunca incluir registros de outra empresa.
8. WHEN a empresa não tem registros THEN o CSV SHALL conter apenas o cabeçalho, com HTTP 200.
9. WHEN a exportação é gerada do mesmo filtro da tela THEN as linhas SHALL corresponder exatamente à tabela principal exibida.

**Independent Test**: exportar cada domínio com/sem período; conferir cabeçalho, linhas, escape, neutralização, nome do arquivo, BOM; repetir sem sessão e como operador.

---

## Edge Cases

- WHEN apenas `de` é informado THEN o sistema SHALL aplicar só o limite inferior, inclusivo.
- WHEN apenas `ate` é informado THEN o sistema SHALL aplicar só o limite superior, inclusivo.
- WHEN `de > ate` THEN o sistema SHALL responder **422** (Q9).
- WHEN `de`/`ate` são inválidos (ex.: `de=abc`) THEN o sistema SHALL responder 422 do framework.
- WHEN a empresa não tem registros THEN o sistema SHALL exibir estado vazio claro, sem erro, e exportar CSV só com cabeçalho (200).
- WHEN `minimo == 0` THEN o sistema SHALL nunca classificar excedente (sem divisão por zero).
- WHEN `peso_kg == 0` THEN a soma da rota SHALL contabilizar zero sem omitir a rota.
- WHEN `avaliacao == 0.0` ou `prazo_dias == 0` THEN o sistema SHALL exibi-los como valores reais, não ausentes.
- WHEN `status` é vazio (string padrão do catálogo) THEN a contagem DEVE agrupá-lo como valor real vazio, não erro.
- WHEN um campo de texto tem `,`, `;`, aspas, quebra de linha ou caractere de controle THEN a exportação SHALL permanecer parseável.
- WHEN o volume de registros é grande THEN as agregações SHALL ser feitas em consultas com `GROUP BY`, sem N+1.
- WHEN um registro é importado durante a geração THEN o resultado SHALL refletir o instante da consulta, sem estado parcial.
- WHEN o dia UTC difere do fuso local THEN o recorte SHALL seguir a regra UTC inclusiva (consistente com /kpis).

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| REL-01 | Schema/Ingestão — `categoria` em `StockItem` + ingestão lê/grava | Design | Pending |
| REL-02 | Schema/Ingestão — `previsao_entrega`/`data_entrega` em `TransportRecord` + ingestão | Design | Pending |
| REL-03 | Schema/Histórico — tabela de histórico por importação + índices | Design | Pending |
| REL-04 | Schema/Histórico — backfill dos catálogos existentes | Design | Pending |
| REL-05 | Schema/Histórico — importação grava snapshot por registro aceito | Design | Pending |
| REL-06 | Estoque P1 AC1/AC6 (página) | Design | Pending |
| REL-07 | Estoque P1 AC2 (abaixo do mínimo) | Design | Pending |
| REL-08 | Estoque P1 AC3 (excedente) | Design | Pending |
| REL-09 | Estoque P1 AC4 (por local) | Design | Pending |
| REL-10 | Estoque P1 AC5 (por categoria) | Design | Pending |
| REL-11 | Transporte P1 AC1/AC5 (página) | Design | Pending |
| REL-12 | Transporte P1 AC2 (por status) | Design | Pending |
| REL-13 | Transporte P1 AC3 (peso por rota) | Design | Pending |
| REL-14 | Transporte P1 AC4 (atrasos) | Design | Pending |
| REL-15 | Fornecedores P1 AC1/AC5 (página) | Design | Pending |
| REL-16 | Fornecedores P1 AC2 (ativo/inativo) | Design | Pending |
| REL-17 | Fornecedores P1 AC3 (avaliação/prazo) | Design | Pending |
| REL-18 | Fornecedores P1 AC4 (por categoria) | Design | Pending |
| REL-19 | Recorte P1 AC1/AC2 (empresa do Membership) | Design | Pending |
| REL-20 | Recorte P1 AC3 (sem período = todo histórico) | Design | Pending |
| REL-21 | Recorte P1 AC4 (UTC inclusivo) | Design | Pending |
| REL-22 | Recorte P1 AC5 (`de == até`) | Design | Pending |
| REL-23 | Recorte P1 AC6 (persistir de/até no form) | Design | Pending |
| REL-24 | Edge — só `de` / só `ate` | Design | Pending |
| REL-25 | Guard P1 AC1 (401 sem sessão) | Design | Pending |
| REL-26 | Guard P1 AC2 (403 operador) | Design | Pending |
| REL-27 | Guard P1 AC3 (200 admin/gestor) | Design | Pending |
| REL-28 | Export P1 AC1/AC7/AC9 (cabeçalho + linhas, mesmo recorte) | Design | Pending |
| REL-29 | Export P1 AC2 (Content-Disposition + nome) | Design | Pending |
| REL-30 | Export P1 AC3 (UTF-8 com BOM) | Design | Pending |
| REL-31 | Export P1 AC4 (RFC 4180) | Design | Pending |
| REL-32 | Export P1 AC5 (neutralização de fórmula) | Design | Pending |
| REL-33 | Export P1 AC8 (header-only 200) | Design | Pending |
| REL-34 | Edge — `de > ate` → 422 | Design | Pending |
| REL-35 | Edge — data inválida → 422 do framework | Design | Pending |
| REL-36 | Edge — agregações em `GROUP BY` (sem N+1) | Design | Pending |
| REL-37 | Edge — empresa sem registros → estado vazio sem erro | Design | Pending |
| REL-38 | Edge — `minimo == 0` sem classificação de excedente | Design | Pending |
| REL-39 | Edge — `peso_kg == 0` conta a rota | Design | Pending |
| REL-40 | Edge — `avaliacao 0.0`/`prazo_dias 0` como valores reais | Design | Pending |

**Story criterion → requirement map**

| Story / critério | Requirements |
| --- | --- |
| Estoque AC1–AC6 | REL-06, REL-07, REL-08 (+REL-38), REL-09, REL-10, REL-21/REL-22 |
| Transporte AC1–AC5 | REL-11, REL-12, REL-13 (+REL-39), REL-14, REL-21/REL-22 |
| Fornecedores AC1–AC5 | REL-15, REL-16, REL-17 (+REL-40), REL-18, REL-21/REL-22 |
| Recorte AC1–AC6 | REL-19, REL-20, REL-21, REL-22, REL-23, REL-24 |
| Guard AC1–AC3 | REL-25, REL-26, REL-27 |
| Export AC1–AC9 | REL-28, REL-29, REL-30, REL-31, REL-32, REL-25/REL-26, REL-28, REL-33, REL-28 |
| Enablers (Q1/Q3/Q6) | REL-01, REL-02, REL-03, REL-04, REL-05 |
| Perf/estado vazio | REL-36, REL-37 |

**Coverage:** 40 requisitos; todos mapeados a tasks em `tasks.md`.

---

## Data Model Changes

### 1. `StockItem` (REL-01)

Nova coluna: `categoria: Mapped[str] = mapped_column(String(60), default="")`.
Backfill implícito: linhas existentes recebem `""` (valor vazio real, não nulo).

### 2. `TransportRecord` (REL-02)

Novas colunas nullable:
- `previsao_entrega: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)`.
- `data_entrega: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)`.

`data_entrega` é necessária para operacionalizar a decisão Q3 ("atraso = entregue após a
previsão"): sem a data efetiva de entrega não há como comparar. É dado derivado da regra
aprovada, não um novo critério de negócio.

### 3. Tabela `catalogo_historico` (REL-03) — snapshot versionado por importação

| Coluna | Tipo | Nulo | Observação |
| --- | --- | --- | --- |
| `id` | Uuid | não | PK |
| `empresa_id` | Uuid | não | FK `empresa.id` |
| `dominio` | String(20) | não | `estoque` \| `fornecedores` \| `transporte` |
| `chave` | String(80) | não | `sku` / `fornecedor_id` / `codigo_rastreio` (uppercase) |
| `import_job_id` | Uuid | sim | FK `import_job.id`; `NULL` no backfill |
| `importado_em` | DateTime(tz) | não | `= job.created_at` na importação; `= now` no backfill |
| `nome` | String(120) | sim | payload do snapshot |
| `categoria` | String(60) | sim | estoque/fornecedores |
| `local` | String(40) | sim | estoque |
| `quantidade` | Integer | sim | estoque |
| `minimo` | Integer | sim | estoque |
| `prazo_dias` | Integer | sim | fornecedores |
| `avaliacao` | Float | sim | fornecedores |
| `ativo` | Boolean | sim | fornecedores |
| `origem` | String(80) | sim | transporte |
| `destino` | String(80) | sim | transporte |
| `peso_kg` | Float | sim | transporte |
| `status` | String(120) | sim | transporte |
| `previsao_entrega` | DateTime(tz) | sim | transporte |
| `data_entrega` | DateTime(tz) | sim | transporte |

**Cardinalidade:** 1 registro de catálogo → N snapshots (um por importação que o aceitou);
1 `ImportJob` → M snapshots (um por registro aceito). O histórico é append-only.

**Índices:**
- `ix_catalogo_historico_empresa_dominio_em` em (`empresa_id`, `dominio`, `importado_em`).
- `ix_catalogo_historico_empresa_dominio_chave` em (`empresa_id`, `dominio`, `chave`, `importado_em`).

**Backfill (REL-04):** na migração, para cada linha existente de `stock_item`/`supplier`/
`transport_record`, inserir um snapshot com `import_job_id = NULL`, `importado_em = now`
e os valores atuais. Garante que os dados pré-migração apareçam no relatório (sem período
= último snapshot por chave).

**Migração Alembic:** nova revision com `down_revision = '9c2f7a41b6d3'` (ver
`alembic/versions/`), adicionando as colunas, criando a tabela e rodando o backfill via
`op.execute(INSERT ... SELECT)` por domínio. `downgrade` remove a tabela, o backfill e as
colunas, nessa ordem.

---

## Process / Background Flow

**Happy path (importação → relatório):**
1. Gestor importa um CSV; `importar` valida e faz upsert nos catálogos (com `categoria` e datas).
2. Para cada registro aceito, grava um snapshot em `catalogo_historico` com `importado_em = job.created_at`.
3. Gestor acessa `/relatorios/{dominio}`; o repositório lê o histórico da empresa, pega o
   último snapshot por chave dentro do período e agrega.
4. Exportação CSV reusa a mesma consulta e serializa a tabela principal.

**Failure path — período inválido (`de > ate`):** a rota responde 422 antes de consultar.
**Failure path — erro de CSV inválido na importação:** `ErroImportacao` antes de qualquer
escrita; catálogo e histórico intactos (transação única).
**Failure path — acesso:** sem sessão → 401; operador → 403; nada é consultado.

---

## API Changes

| Método | Rota | Guard | Resposta |
| --- | --- | --- | --- |
| GET | `/relatorios/estoque` | admin/gestor | HTML `relatorios.html` |
| GET | `/relatorios/transporte` | admin/gestor | HTML `relatorios.html` |
| GET | `/relatorios/fornecedores` | admin/gestor | HTML `relatorios.html` |
| GET | `/relatorios/{dominio}/exportar` | admin/gestor | CSV (`text/csv; charset=utf-8`) |

- `desde`/`ate` são `date | None`; convertidos em limites UTC inclusivos (`time.min`/`time.max`).
- `{dominio}` fora de `{estoque, transporte, fornecedores}` → 404.
- `de > ate` → 422. Data inválida → 422 (framework).
- Nome do arquivo: `relatorio-{dominio}-{de}_{ate}.csv`, com datas ausentes omitidas
  (só `de` → `relatorio-{dominio}-{de}.csv`; só `ate` → `relatorio-{dominio}-{ate}.csv`;
  nenhuma → `relatorio-{dominio}.csv`).

---

## Frontend Changes

- Template `web/templates/relatorios.html`: form GET com `.form-periodo` (campos `desde`/`ate`,
  valores persistidos), tabela principal e blocos de agregação por domínio.
- Rótulos PT (Q11): estoque → colunas `SKU`, `Nome`, `Categoria`, `Local`, `Quantidade`,
  `Mínimo`, `Situação` com valores `Abaixo do mínimo` / `Excedente` / `Normal`; blocos
  `Itens por local` e `Itens por categoria`. Transporte → `Código de rastreio`, `Origem`,
  `Destino`, `Peso (kg)`, `Status`, `Previsão de entrega`, `Data de entrega`, `Situação`
  (`Atrasado`/`No prazo`); blocos `Registros por status` e `Peso por rota`. Fornecedores →
  `Fornecedor`, `Nome`, `Categoria`, `Prazo (dias)`, `Avaliação`, `Status` (`Ativo`/`Inativo`);
  blocos `Distribuição por situação`, `Indicadores` e `Fornecedores por categoria`.
- CSS novo em `web/static/relatorios.css` (o `app.css` já tem 802 linhas — teto de 800),
  referenciado por `{% block %}`/link no template de relatórios.
- Link de navegação "Relatórios" em `base.html` (visível a admin/gestor via `pode_aprovar`),
  apontando para `/relatorios/estoque`. Deve preservar `tests/web/test_shell.py` e
  `tests/web/test_app.py`.

**Semântica do CSV:** o CSV exporta a **tabela principal** do domínio (uma linha por registro
do período, com a coluna `Situação`), com o mesmo cabeçalho exibido. Os blocos de agregação
são apenas de tela — decisão que torna coerente o requisito "empresa sem dados → CSV só com
cabeçalho" (Q12). A decisão Q11 define os rótulos usados tanto na tela quanto nos cabeçalhos
do CSV.

---

## Tests Required

**Unit**
- `tests/ingestion/test_parser.py`: estoque lê `categoria` (default `""`); transporte lê
  `previsao_entrega`/`data_entrega` (ISO e `DD/MM/YYYY`; vazio → `None`).
- `tests/test_csv_relatorios.py` (novo): separador `;`, BOM (`utf-8-sig`), escape RFC 4180,
  neutralização de `= + - @`, nome do arquivo com/sem datas, header-only.

**Integration**
- `tests/test_migrations.py` (existente): nova revision sobe até head; `catalogo_historico`
  e colunas existem; índices; downgrade remove a tabela.
- `tests/test_repositories.py` / novo `tests/test_repositories_relatorios.py`: agregações por
  domínio (abaixo/excedente/situação, por local/categoria, por status, peso por rota com zero,
  atrasos, ativo/inativo, indicadores, por categoria); isolamento por empresa; recorte
  inclusivo (`de==ate`, só `de`, só `ate`); último snapshot por chave vence.
- `tests/ingestion/test_servico.py`: importação grava snapshot por registro aceito; rejeitadas
  não geram snapshot; `categoria`/datas persistem no catálogo.
- `tests/web/test_relatorios.py` (novo): 401/403/200 nas 4 rotas; render das tabelas e
  rótulos; persistência de `de`/`ate`; `de > ate` → 422; data inválida → 422; domínio
  inválido → 404; export: `Content-Disposition`, BOM, linhas == tela, header-only 200,
  isolamento entre tenants, `empresa_id` alheio ignorado.

**Edge case**
- `minimo == 0` não classifica excedente; `peso_kg == 0` mantém a rota; `avaliacao 0.0` e
  `prazo_dias 0` exibidos; campos com `;`/aspas/quebra de linha parseáveis.

**Existing tests that will break**
- `tests/web/test_shell.py` e `tests/web/test_app.py` se `base.html` for alterado de forma
  incorreta (link novo deve ser aditivo e não quebrar integridade de CDN/`app.css`).
- `tests/ingestion/test_parser.py`/`test_servico.py` se as assinaturas de `upsert` mudarem
  sem atualizar os chamadores.

---

## Files That Will Change

| File | Change type | Why |
| --- | --- | --- |
| `src/gestlog/db/models.py` | modify | `categoria` em `StockItem`; datas em `TransportRecord`; `CatalogoHistorico` |
| `alembic/versions/<nova>_relatorios_historico.py` | add | colunas + tabela + índices + backfill |
| `src/gestlog/ingestion/modelos.py` | modify | `categoria` em `RegistroEstoque`; datas em `RegistroTransporte` |
| `src/gestlog/ingestion/parser.py` | modify | ler `categoria`/datas (helper de data) |
| `src/gestlog/repositories/catalog.py` | modify | `upsert` com `categoria` e datas |
| `src/gestlog/ingestion/servico.py` | modify | passar campos novos; gravar snapshots |
| `src/gestlog/repositories/historico.py` | add | inserir/consultar snapshots |
| `src/gestlog/repositories/relatorios.py` | add | agregações por domínio + dataclasses |
| `src/gestlog/repositories/__init__.py` | modify | reexportar repositórios/dataclasses |
| `src/gestlog/web/relatorios.py` | add | rotas de página e export |
| `src/gestlog/web/csv_relatorios.py` | add | serialização CSV (stdlib) |
| `src/gestlog/web/templates/relatorios.html` | add | página por domínio |
| `src/gestlog/web/templates/base.html` | modify | link "Relatórios" |
| `src/gestlog/web/static/relatorios.css` | add | estilos das tabelas/agregações |
| `src/gestlog/web/app.py` | modify | registrar router |
| `src/gestlog/web/__init__.py` | modify | reexportar router |
| `tests/...` | add/modify | ver Tests Required |

---

## Risks

- **Timezone:** recorte precisa ser UTC inclusivo (`time.min`/`time.max`), como /kpis;
  desvio de fuso muda o conjunto.
- **Multi-tenancy:** empresa sempre do `Membership`; `empresa_id` do cliente é ignorado;
  toda query filtra por `empresa_id`. Testar isolamento com dois tenants.
- **Semântica do histórico:** "último snapshot por chave no período" pode divergir de
  "todos os snapshots"; a especificação fixa último-por-chave (dedup) para evitar duplicatas.
  Empates de `importado_em` para mesma chave são raros, mas o desempate não é totalmente
  determinístico (mesmo padrão de AD-028).
- **Backfill:** sem ele, dados pré-migração somem dos relatórios; migração precisa rodar
  backfill por domínio e ser idempotente o suficiente para rodar uma única vez.
- **CSV injection / RFC 4180:** neutralizar apenas campos de texto; numéricos não recebem
  prefixo. Escapar `;`/aspas/quebras com `csv.writer`.
- **N+1:** agregações em `GROUP BY`; a seleção do último snapshot por chave usa subconsulta
  agrupada, não laço por registro.
- **Tetos de código:** `app.css` já em 802 linhas → novo `relatorios.css`; arquivos ≤ 800
  linhas e funções ≤ 50 (AGENTS.md). Repositório de relatórios pode exigir módulos por domínio.
- **Regressão de shell:** alterar `base.html` pode quebrar `test_shell.py`/`test_app.py`;
  o link deve ser aditivo e não mexer em CDN/`app.css`.
- **`data_entrega`:** necessária para Q3; se a ingestão não fornecer, atraso = 0. Documentado.

---

## Open Questions

None. As 12 questões foram resolvidas no Checkpoint 1 (tabela "Decisões aprovadas" da
`story.md`). A única inferência técnica — `data_entrega` como par de `previsao_entrega`
para operacionalizar Q3 — está justificada em Data Model Changes.

---

## Success Criteria

- [ ] `/relatorios/{estoque,transporte,fornecedores}` renderizam 200 para admin/gestor,
      401 sem sessão e 403 para operador.
- [ ] Relatórios isolam por empresa e aplicam recorte de/até inclusivo (UTC), com
      `de == até` cobrindo o dia.
- [ ] Agregações por domínio conferem com os dados semeados (abaixo/excedente, por
      local/categoria, por status, peso por rota, atrasos, ativo/inativo, indicadores).
- [ ] Exportação serve CSV `;`/UTF-8-BOM com nome e recorte corretos, escapado e
      neutralizado, header-only 200 para empresa vazia.
- [ ] Gate completo (`black --check`, `ruff check`, `pytest`) verde, com cobertura ≥ 80%.
