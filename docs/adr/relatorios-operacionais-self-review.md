# ADR: relatorios-operacionais

## 1. Contexto & Objetivo

O dashboard `/kpis` (AD-028) responde bem "como está a operação em números", mas o
gestor continuava sem o que existe em qualquer operação logística real: **uma
tabela por domínio, recortada por período e exportável**. O pedido parecia só uma
tela nova, mas esbarrava no alicerce de dados: `StockItem`, `Supplier` e
`TransportRecord` guardam apenas a **última** versão importada e nunca tiveram
timestamp, então não havia como responder "o que existia entre 1º e 30 de junho" —
o catálogo simplesmente não reconstrói o passado. A feature `relatorios-operacionais`
resolve isso para os três domínios (`estoque`, `transporte`, `fornecedores`), com
recorte de/até **UTC inclusivo**, guarda `admin`/`gestor` e exportação CSV, sob os
requisitos REL-01..REL-40. A meta arquitetural central foi introduzir
**rastreabilidade temporal** sem transformar os catálogos em tabelas temporais
complexas e sem abrir mão do confinamento de SQL à camada `libs` nem do
isolamento estrito entre empresas (a empresa vem sempre do `Membership` da
sessão, e `empresa_id` vindo do cliente é ignorado).

## 2. Decisões de Arquitetura

**1. Histórico versionado por importação em vez de um timestamp único no catálogo**

A alternativa fácil seria adicionar um `updated_at` a cada catálogo, mas um único
timestamp só diz "isto mudou", não "isto valia no período X" — e um item
reimportado várias vezes perderia o estado intermediário, justamente o que o
recorte exige. A decisão foi criar `CatalogoHistorico`
(`src/gestlog/db/models.py`) e gravar **um snapshot por registro aceito e por
importação**, em `HistoricoRepository.registrar(job, dominio, chave, **payload)`
com `importado_em = job.created_at`. A granularidade "1 linha por registro aceito"
(respostas Q1/Q5/Q6) preserva os valores no tempo sem multiplicar colunas por
campo, e amarra cada versão ao `import_job_id` que a produziu — o histórico é
*append-only*, ou seja, nada é sobrescrito e a trilha de auditoria fica
preservada. Para o negócio, isso significa que o relatório de junho mostra o
estoque de junho mesmo que julho tenha reimportado tudo. A escrita do snapshot
acontece no mesmo fluxo transacional de `ingestion/servico.py::_aplicar_registros`,
então uma importação rejeitada não gera snapshot e uma falha de arquivo deixa
catálogo e histórico intactos.

**2. "Último snapshot por chave no período" para deduplicar sem inventar série temporal**

Guardar todas as versões cria um risco imediato: um SKU reimportado três vezes
apareceria três vezes na tabela. A especificação (Q6) fixou a semântica **"último
snapshot de cada `chave` dentro do período"**, implementada em uma única consulta
em `HistoricoRepository.ultimo_por_chave`: uma subconsulta agrupada faz
`GROUP BY chave, MAX(importado_em)` e o `SELECT` externo faz join por
`(chave, importado_em)`, reaplicando os mesmos filtros de empresa, domínio e
período. O efeito prático é uma foto **por registro**, não uma série: o gestor vê
cada item uma vez, no estado mais recente dentro da janela escolhida. Sem período,
o `MAX` por chave devolve naturalmente o estado mais recente de todo o histórico
(REL-20). Nenhuma agregação roda em laço por registro — todas usam `GROUP BY` em
`RelatorioRepository` (`_contagens`, `_peso_por_rota`, `_medias`), o que fecha o
risco de N+1 apontado na spec (REL-36).

**3. `data_entrega` como par de `previsao_entrega`, derivado da regra aprovada**

A decisão Q3 definiu atraso como "entregue após a previsão", mas a previsão
sozinha não permite comparar com a realidade. Como a spec registra explicitamente,
`data_entrega` não é um critério novo de negócio, e sim o dado necessário para
**operacionalizar** Q3: `RegistroTransporte.atrasado` é verdadeiro apenas quando
`data_entrega > previsao_entrega` **e ambas estão preenchidas**, e
`ResumoTransporte.atrasos` conta esses casos. Se a ingestão não trouxer a data, o
registro simplesmente não é contado como atrasado (`False`), nunca como erro. Os
dois campos entram como colunas nullable `DateTime(timezone=True)` em
`TransportRecord` e como campos opcionais em `RegistroTransporte`/`parser._data`,
que aceita ISO e `DD/MM/YYYY` e devolve `None` para vazio.

**4. O CSV exporta exatamente a tabela principal, não os blocos de agregação**

Havia uma ambiguidade real: um CSV "completo" poderia tentar achatar tabela +
agregações em um arquivo só, mas isso produziria um formato irregular e difícil de
parsear. A decisão Q12 foi exportar **só a tabela principal**, com a coluna
`Situação`, e usar os mesmos rótulos da tela (`_CABECALHOS` em
`src/gestlog/web/relatorios.py`, a decisão Q11) tanto no `<thead>` quanto no
cabeçalho do CSV. Isso torna coerente o requisito "empresa sem dados → CSV só com
cabeçalho, HTTP 200" (REL-33) e a promessa de que "as linhas correspondem
exatamente à tabela exibida" (REL-28/AC9). A serialização fica isolada em
`src/gestlog/web/csv_relatorios.py`, com `;`, `utf-8-sig` (BOM para o Excel
pt-BR), `csv.writer` com `lineterminator="\r\n"` (RFC 4180) e
`neutralizar()`, que prefixa `'` em textos iniciados por `= + - @` ou tab/CR —
apenas em `str`, de modo que campos numéricos permanecem intactos e não viram
fórmula no Excel.

**5. Backfill portável dentro da migração, para não apagar o passado pré-feature**

Se a migração criasse a tabela mas não populasse nada, todo o dato importado antes
da feature sumiria dos relatórios. A revisão `c4a81f0d9e2b` (com
`down_revision = '9c2f7a41b6d3'`) faz `INSERT ... SELECT` por domínio em
`_backfill()`, gravando um snapshot por linha existente com `import_job_id = NULL`
e `importado_em` via bind param `:agora = datetime.now(UTC)` — aware e com
microssegundos, no mesmo formato das linhas vivas (`job.created_at`), capturado uma
única vez para os três domínios — ou seja, o dado antigo aparece como a
versão mais recente sem poluir o histórico ligado a importações reais. O `id` do
snapshot é gerado por `_uuid_sql()`, que checa `op.get_bind().dialect.name` e usa
`gen_random_uuid()` no Postgres e `lower(hex(randomblob(16)))` no SQLite,
mantendo a migração executável tanto no banco de produção quanto nos testes
(Alembic sobre SQLite). O `downgrade` desfaz na ordem inversa: índices, tabela e
colunas.

**6. Fronteira `apps → agents → libs` preservada: SQL só no repositório**

As rotas em `src/gestlog/web/relatorios.py` (camada `apps`) não conhecem SQL:
elas validam domínio e período, resolvem a empresa via
`exigir_papel(*PAPEIS_APROVADORES)` e chamam `RelatorioRepository`. A validação
`_validar_dominio` responde **404** para domínio fora de
`{estoque, transporte, fornecedores}` e `_validar_periodo` responde **422** quando
`de > ate` (Q9); datas malformadas já são 422 do próprio FastAPI. O recorte de
data vira instantes UTC inclusivos reutilizando `inicio_do_dia`/`fim_do_dia` de
`web/periodo.py` (`time.min`/`time.max` com `tzinfo=UTC`), fonte única também
consumida por `web/kpis.py` e `web/correcoes.py` (FU-1), o que mantém o
comportamento consistente entre os routers.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **Histórico cresce por importação:** um snapshot por registro aceito aumenta o
  volume em função do número de importações × registros. A alternativa (tabela
  temporal bitemporal completa, ou diffs por campo) foi rejeitada por
  desproporcional ao MVP. Aceitável porque o custo é linear, os índices
  `ix_catalogo_historico_empresa_dominio_em` e `..._chave` cobrem o padrão de
  leitura (empresa + domínio + tempo + chave) e o histórico é o próprio registro
  de auditoria que a spec pedia. A evolução natural, se o volume crescer, é
  particionar por `importado_em` ou aplicar retenção sobre snapshots antigos.
* **Desempate não determinístico em empates de `importado_em`:** se dois snapshots
  da mesma chave tiverem exatamente o mesmo timestamp, o join por `MAX` pode
  devolver ambos. É o mesmo padrão já aceito em AD-028 e o design o registra: na
  prática, `importado_em` é o `created_at` do job e snapshots da mesma importação
  compartilham o instante, mas cada chave aparece uma vez por importação; o caso
  patológico exigiria reimportações com colisão de relógio. A correção definitiva
  (desempate por `importado_em, id`) fica registrada para quando for necessária.
* **`de > ate` responde 422 explícito, distinto do 422 do framework:** a distinção
  foi escolha de produto (Q9) para dar mensagem clara (`"Período inválido: 'de' é
  posterior a 'ate'."`) sem alterar a UX dos demais erros de validação.
* **Tela não faz paginação:** a tabela carrega todas as linhas vigentes do período
  de uma vez. Para o volume atual é adequado e mantém o requisito "linhas do CSV
  == linhas da tela" trivial de garantir; paginação é uma melhoria futura que
  exigiria exportar o conjunto completo mesmo assim.
* **Fuso do tenant não é considerado:** o recorte segue UTC, consistente com
  `/kpis`. Se o produto passar a operar multi-fuso, `_inicio`/`_fim` precisarão
  converter a partir do fuso cadastrado na empresa.

**Limitações conhecidas:**
- T11 (testes de aceitação P1 ponta a ponta, `tests/acceptance/test_relatorios_p1.py`)
  ainda não foi executada; a fase de integração do plano de tasks cobre T1–T10 e o
  aceite E2E fica para o próximo passo.
- Cabeçalhos de agregação (`Itens por local`, etc.) não têm validação cruzada
  automática com a spec além dos testes HTTP existentes.

## 4. O que vem a seguir (Roadmap Imediato)

* **T11 (aceitação P1):** um teste por critério nomeado da história, com fluxo HTTP
  real e dois tenants, verificando o CSV byte a byte (BOM/`;`) — é o gate `full`
  que fecha REL-01..REL-40 ponta a ponta.
* **Paginação/retenção do histórico:** se o volume de snapshots crescer, particionar
  `catalogo_historico` por `importado_em` e expurgar snapshots fora da janela de
  retenção da `Empresa`.
* **Filtros adicionais (fora de escopo na v1):** local/categoria/status foram
  deliberadamente deixados de fora; o repositório já está estruturado por domínio
  para recebê-los sem reescrita.
* **Desempate determinístico:** trocar o join por `(importado_em, id)` quando a
  auditoria exigir ordem à prova de empate.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio e privacidade:** o `empresa_id` é sempre derivado do
  `Membership` resolvido por `exigir_papel`, nunca da URL/query; todas as consultas
  filtram por `empresa_id` na subconsulta e no `SELECT` externo. O teste
  `test_relatorios_isolam_entre_tenants_e_ignoram_empresa_id` prova que
  `empresa_id` alheio é ignorado tanto na tela quanto na exportação, e
  `test_export_fornecedor_fora_da_empresa_nao_aparece` cobre o CSV. Sem sessão →
  401; `operador` → 403; `admin`/`gestor` → 200 (REL-25..REL-27). As consultas usam
  ORM parametrizado (sem concatenação de SQL) e o CSV neutraliza injeção de
  fórmula, o único "input hostil" que chega ao arquivo.
* **Cobertura e testes automatizados:** `tests/test_repositories_relatorios.py`
  (agregações por domínio, exclusão, recorte `de == ate`, só `de`/só `ate`, último
  snapshot vence, vazio), `tests/web/test_relatorios.py` (401/403/200, render,
  persistência de período, 404/422, export com BOM/`;`/nome/header-only,
  isolamento), `tests/test_csv_relatorios.py` (BOM, RFC 4180, neutralização, nome),
  `tests/test_migrations.py` (head, colunas, índices, downgrade, backfill) e
  `tests/ingestion` (categoria, datas ISO/brasileira, snapshot só dos aceitos).
  Gate completo: **490 passed, 99,19%** de cobertura.
* **Padrões de qualidade:** `uv run black --check src/ tests/` → 128 arquivos
  inalterados; `uv run ruff check src/ tests/` → All checks passed. Docstrings e
  nomes em português, `from __future__ import annotations` em todos os módulos,
  sem comentários fora de docstring, sem `print`, funções abaixo de 50 linhas e
  arquivos abaixo de 800 linhas (o CSS ganhou `relatorios.css` próprio porque
  `app.css` já estava em 802 linhas).

## Achados corrigidos no self-review

* **Datas de transporte divergiam entre tela e CSV (média):** a tela renderizava o
  `datetime` cru (`{{ registro.previsao_entrega }}` → `2026-06-10 00:00:00+00:00`)
  enquanto o CSV usava `.isoformat()` (`2026-06-10T00:00:00`). Como o requisito
  REL-28/AC9 exige que as linhas correspondam exatamente à tabela exibida, o
  template passou a usar o mesmo formatador do CSV
  (`{{ registro.previsao_entrega.isoformat() if registro.previsao_entrega else "" }}`),
  coberto por `test_pagina_e_csv_transporte_exibem_mesma_data`.
* **Cabeçalhos triplicados (baixa):** os nomes das colunas existiam em
  `_CABECALHOS` (Python) e repetidos nos três `<thead>` do template. O template
  passou a consumir `cabecalhos` (derivado da mesma fonte), eliminando a chance de
  a tela e o CSV divergirem de cabeçalho.
* **Tipagem de dispatchers e genéricos (baixa):** `_resumo` e `_cabecalho_linhas`
  ficaram sem anotação de retorno/parâmetro, apagando a união real de retorno;
  passaram a usar `_Resumo = ResumoEstoque | ResumoTransporte | ResumoFornecedores`.
  Métodos do histórico ganharam `Select[tuple[CatalogoHistorico]]` e
  `list[ColumnElement[bool]]` no lugar de `Select`/`list` nus.
* **Sem achados** de segurança (segredo hardcoded, SQL injection, XSS, CSRF,
  injeção de prompt), de vazamento entre empresas, de `print`, de função > 50
  linhas ou arquivo > 800 linhas.
* **Limitação aceita, não bloqueante:** o desempate por `(importado_em, id)` em
  empates de snapshot fica documentado; o backfill grava `importado_em` com
  `datetime.now(UTC)` aware/microssegundos (bind param `:agora`), alinhado ao dado
  pré-feature, que aparece como versão corrente — coerente com REL-04.
