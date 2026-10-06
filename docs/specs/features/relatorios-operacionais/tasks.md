# Relatórios operacionais por domínio — Tasks

**Design:** `docs/specs/features/relatorios-operacionais/design.md`
**Spec:** `docs/specs/features/relatorios-operacionais/spec.md`
**Status:** Implemented (T1–T11) · code review PR #66 ✅ (0 Critical/0 Important, 5 Minor) — 2026-09-30
**TLC scope:** complex

> Notas de gate (de `docs/specs/codebase/TESTING.md` e `AGENTS.md`):
> `quick` = `uv run pytest <caminho> --no-cov -q`; `full` = `uv run pytest` (gate de
> cobertura 80%); `lint` = `uv run ruff check src/ tests/ alembic/`; `format` =
> `uv run black --check src/ tests/ alembic/`. Execuções focadas exigem `--no-cov`.
> Um PR por task contra a branch de integração `feat/relatorios-operacionais`.

---

## Execution Plan

### Phase 1: Fundação de dados (Sequential)

```
T1 → T2 → T3
```

### Phase 2: Núcleo (T7 em paralelo; T4→T5→T6 sequencial no mesmo arquivo)

```
T2 ─┬→ T4 → T5 → T6
    └→ T7 [P]  (CSV é stdlib, independente do repositório)
```

### Phase 3: Integração (Sequential)

```
T4,T5,T6,T7 → T8 → T9
                 T8,T7 → T10 → T11
```

---

## Task Breakdown

### T1: Migração de schema + ingestão de `categoria`/datas

**What**: Adicionar `categoria` a `StockItem` e `previsao_entrega`/`data_entrega` a
`TransportRecord`; ler/gravar esses campos na ingestão.
**Where**: `src/gestlog/db/models.py`, `alembic/versions/<nova>_relatorios_historico.py`,
`src/gestlog/ingestion/{modelos,parser}.py`, `src/gestlog/repositories/catalog.py`,
`src/gestlog/ingestion/servico.py`
**Depends on**: None
**Reuses**: `upsert` existentes, `_texto`/`_decimal` do parser, padrão de migração da
revision `9c2f7a41b6d3`
**Requirement**: REL-01, REL-02

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Modelos com as colunas novas (`categoria` default `""`; datas `DateTime(timezone=True)` nullable).
- [x] Nova revision Alembic (`down_revision = '9c2f7a41b6d3'`) com `add_column` (e `downgrade` correspondente).
- [x] `RegistroEstoque.categoria`, `RegistroTransporte.previsao_entrega`/`data_entrega`; parser aceita ISO e `DD/MM/YYYY`, vazio → default.
- [x] `StockRepository.upsert`/`TransportRepository.upsert` gravam os campos novos; `servico` repassa.
- [x] Gate check passa: `uv run pytest tests/ingestion tests/test_migrations.py --no-cov -q`
- [x] Gate check passa: `uv run ruff check src/ tests/` e `uv run black --check src/ tests/`
- [x] Test count: nenhum teste removido; novos testes de parser + migração passam

**Tests**: integration + unit
**Gate**: quick

**Commit**: `feat(relatorios): adiciona categoria no estoque e datas no transporte`

---

### T2: Tabela de histórico por importação + backfill

**What**: Criar `catalogo_historico` (colunas/índices do design) e backfill dos catálogos existentes.
**Where**: `src/gestlog/db/models.py`, `alembic/versions/<nova>_relatorios_historico.py`
**Depends on**: T1
**Reuses**: `Index`, `DateTime(timezone=True)`, `op.execute` do Alembic
**Requirement**: REL-03, REL-04

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Modelo `CatalogoHistorico` com os campos e os dois índices (`..._em`, `..._chave`).
- [x] Migração cria a tabela e os índices; backfill insere 1 snapshot por linha existente, `import_job_id=NULL`, `importado_em=now`.
- [x] `downgrade` remove índices, tabela e (se aplicável) reverte o backfill.
- [x] Gate check passa: `uv run pytest tests/test_migrations.py --no-cov -q`
- [x] Test count: testes de migração (head, colunas/índices, downgrade) passam

**Tests**: integration
**Gate**: quick

**Commit**: `feat(relatorios): cria histórico versionado por importação`

---

### T3: Snapshot na importação

**What**: Gravar um snapshot por registro aceito, ligado ao `ImportJob`.
**Where**: `src/gestlog/repositories/historico.py` (novo), `src/gestlog/ingestion/servico.py`,
`src/gestlog/repositories/__init__.py`
**Depends on**: T2
**Reuses**: `ImportJobRepository.create_job` (created_at), `_aplicar_registros`
**Requirement**: REL-05

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `HistoricoRepository.registrar(job, dominio, chave, **payload)` insere 1 snapshot.
- [x] `importar` grava snapshot só para registros aceitos (rejeitados não geram).
- [x] `importado_em == job.created_at`; demais campos do domínio preenchidos, resto nulo.
- [x] Gate check passa: `uv run pytest tests/ingestion/test_servico.py --no-cov -q`
- [x] Test count: teste de snapshot (aceito/rejeitado) passa

**Tests**: integration
**Gate**: quick

**Commit**: `feat(relatorios): registra snapshot do catálogo a cada importação`

---

### T4: `RelatorioRepository` — estoque

**What**: Agregar o relatório de estoque a partir do histórico (último snapshot por chave no período).
**Where**: `src/gestlog/repositories/relatorios.py` (novo), `src/gestlog/repositories/__init__.py`
**Depends on**: T2
**Reuses**: `select/group_by`, padrão `dataclass(frozen=True)` de `kpis.py`, subconsulta do design
**Requirement**: REL-06, REL-07, REL-08, REL-09, REL-10, REL-37, REL-38

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `estoque(empresa_id, desde, ate) -> ResumoEstoque` com itens, `abaixo_minimo`,
      `excedentes`, `por_local`, `por_categoria`.
- [x] Excedente = `minimo > 0 and quantidade > minimo * 2`.
- [x] Consultas com `GROUP BY`; sem N+1; filtro por `empresa_id`.
- [x] Empresa sem dados → resumo vazio.
- [x] Gate check passa: `uv run pytest tests/test_repositories_relatorios.py --no-cov -q`
- [x] Test count: testes de agregação, período inclusivo, isolamento e excedente passam

**Tests**: integration
**Gate**: quick

**Commit**: `feat(relatorios): agrega relatório de estoque por período`

---

### T5: `RelatorioRepository` — transporte

**What**: Agregar o relatório de transporte (por status, peso por rota, atrasos).
**Where**: `src/gestlog/repositories/relatorios.py` (modify)
**Depends on**: T4
**Reuses**: leitura de histórico de T4
**Requirement**: REL-11, REL-12, REL-13, REL-14, REL-39

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `transporte(...) -> ResumoTransporte` com registros, `por_status`, `peso_por_rota`, `atrasos`.
- [x] Peso agrupado por `(origem, destino)`; rota com `peso_kg == 0` não é omitida.
- [x] Atraso = `data_entrega > previsao_entrega` (ambos preenchidos).
- [x] Gate check passa: `uv run pytest tests/test_repositories_relatorios.py --no-cov -q`
- [x] Test count: testes de status, rota (incl. zero), atraso e período passam

**Tests**: integration
**Gate**: quick

**Commit**: `feat(relatorios): agrega relatório de transporte por período`

---

### T6: `RelatorioRepository` — fornecedores

**What**: Agregar o relatório de fornecedores (distribuição, indicadores, por categoria).
**Where**: `src/gestlog/repositories/relatorios.py` (modify)
**Depends on**: T5
**Reuses**: leitura de histórico de T4
**Requirement**: REL-15, REL-16, REL-17, REL-18, REL-40

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `fornecedores(...) -> ResumoFornecedores` com `fornecedores`, `ativos`, `inativos`,
      `avaliacao_media`, `prazo_medio`, `por_categoria`.
- [x] `avaliacao 0.0` e `prazo_dias 0` contam nos indicadores como valores reais.
- [x] Gate check passa: `uv run pytest tests/test_repositories_relatorios.py --no-cov -q`
- [x] Test count: testes de distribuição, indicadores, por categoria e período passam
- [x] Arquivo `relatorios.py` ≤ 800 linhas (senão extrair módulo por domínio)

**Tests**: integration
**Gate**: quick

**Commit**: `feat(relatorios): agrega relatório de fornecedores por período`

---

### T7: Módulo de CSV (stdlib) [P]

**What**: Serializar a tabela principal em CSV `;`, UTF-8 com BOM, RFC 4180 e anti-injeção.
**Where**: `src/gestlog/web/csv_relatorios.py` (novo)
**Depends on**: None
**Reuses**: `csv`, `io` da stdlib; `_FATOR_EXCEDENTE` como referência de rótulos
**Requirement**: REL-28, REL-29, REL-30, REL-31, REL-32, REL-33

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `gerar_csv(cabecalho, linhas) -> bytes` usa `;`, `csv.writer`, codifica `utf-8-sig`.
- [x] `neutralizar` prefixa `'` para valores iniciados por `= + - @` (e tab/CR); numéricos intactos.
- [x] `nome_arquivo(dominio, desde, ate)` = `relatorio-{dominio}[-{de}][_{ate}].csv` com datas ausentes omitidas.
- [x] Cabeçalho + zero linhas → bytes só com cabeçalho.
- [x] Gate check passa: `uv run pytest tests/test_csv_relatorios.py --no-cov -q`
- [x] Test count: testes de formato, escape, neutralização, nome e header-only passam

**Tests**: unit
**Gate**: quick

**Commit**: `feat(relatorios): gera CSV com separador ; e UTF-8 com BOM`

---

### T8: Rotas de página + guard + período + template

**What**: Registrar `GET /relatorios/{dominio}` para os 3 domínios, com guard admin/gestor,
validação de período e render de `relatorios.html`.
**Where**: `src/gestlog/web/relatorios.py` (novo), `src/gestlog/web/templates/relatorios.html`
(novo), `src/gestlog/web/app.py`, `src/gestlog/web/__init__.py`
**Depends on**: T4, T5, T6
**Reuses**: `web/kpis.py` (guard, `_inicio`/`_fim`, `Jinja2Templates`), `get_sync_session`
**Requirement**: REL-06, REL-11, REL-15, REL-19, REL-20, REL-21, REL-22, REL-23, REL-24, REL-25, REL-26, REL-27, REL-34, REL-35, REL-37

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Router registrado no `create_app` e reexportado em `web/__init__.py`.
- [x] `{dominio}` inválido → 404; `de > ate` → 422; data inválida → 422 (framework).
- [x] Empresa sempre de `exigir_papel(*PAPEIS_APROVADORES)` (401 sem sessão; 403 operador).
- [x] Template com `.form-periodo` (persistindo `desde`/`ate`) e tabela principal + agregações por domínio.
- [x] Gate check passa: `uv run pytest tests/web/test_relatorios.py --no-cov -q`
- [x] Test count: testes de 401/403/200, render, período e validação passam

**Tests**: integration
**Gate**: quick

**Commit**: `feat(relatorios): adiciona rotas de página por domínio`

---

### T9: Estilos e navegação

**What**: CSS próprio em `relatorios.css` e link "Relatórios" no shell.
**Where**: `src/gestlog/web/static/relatorios.css` (novo), `src/gestlog/web/templates/base.html`,
`src/gestlog/web/templates/relatorios.html`
**Depends on**: T8
**Reuses**: classes `.pagina`, `.painel-tabela`, `.chip`, `.form-periodo`
**Requirement**: REL-06, REL-11, REL-15, REL-23

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `relatorios.css` linkado no template; `app.css` intocado (teto de linhas).
- [x] Link "Relatórios" visível só com `pode_aprovar`, apontando para `/relatorios/estoque`.
- [x] Gate check passa: `uv run pytest tests/web/test_shell.py tests/web/test_app.py tests/web/test_relatorios.py --no-cov -q`
- [x] Test count: testes de shell/app inalterados e verdes (nenhuma remoção)

**Tests**: integration
**Gate**: quick

**Commit**: `feat(relatorios): estiliza relatórios e adiciona navegação`

---

### T10: Rota de exportação CSV

**What**: `GET /relatorios/{dominio}/exportar` servindo o CSV da tabela principal com o mesmo recorte.
**Where**: `src/gestlog/web/relatorios.py` (modify), `src/gestlog/web/csv_relatorios.py`
**Depends on**: T7, T8
**Reuses**: `RelatorioRepository`, `nome_arquivo`/`gerar_csv`, `Response`
**Requirement**: REL-25, REL-26, REL-27, REL-28, REL-29, REL-30, REL-31, REL-32, REL-33

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Resposta `text/csv; charset=utf-8` com `Content-Disposition: attachment; filename="..."`.
- [x] Linhas exportadas == tabela principal da tela; BOM presente; escape/neutralização aplicados.
- [x] Empresa sem registros → CSV header-only 200; isolamento entre tenants mantido.
- [x] Gate check passa: `uv run pytest tests/web/test_relatorios.py --no-cov -q`
- [x] Gate check passa: `uv run ruff check src/ tests/` e `uv run black --check src/ tests/`
- [x] Test count: testes de export (nome, BOM, escape, injeção, vazio, 401/403) passam

**Tests**: integration
**Gate**: quick

**Commit**: `feat(relatorios): exporta CSV por domínio com mesmo recorte`

---

### T11: Testes de aceitação P1

**What**: Provar ponta a ponta os critérios P1 dos 7 grupos da história.
**Where**: `tests/acceptance/test_relatorios_p1.py` (novo)
**Depends on**: T9, T10
**Reuses**: fixtures de `tests/web/test_kpis.py`, `tests/acceptance/` (modelo fake não necessário)
**Requirement**: REL-01..REL-40

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Um teste por critério nomeado (estoque, transporte, fornecedores, recorte, guard, export, enablers).
- [x] Fluxo HTTP real; dois tenants para isolamento; CSV verificado byte a byte (BOM/`;`).
- [x] Gate check passa: `uv run pytest` (full, cobertura ≥ 80%)
- [x] Test count: suíte completa verde, sem regressões

**Tests**: e2e
**Gate**: full

**Commit**: `test(relatorios): aceitação P1 ponta a ponta`

---

## Parallel Execution Map

```
Phase 1 (Sequential):
  T1 ──→ T2 ──→ T3

Phase 2 (T7 paralelo; T4→T6 sequencial — mesmo arquivo):
  T2 complete, then:
    ├── T4 ──→ T5 ──→ T6
    └── T7 [P]

Phase 3 (Sequential):
  T4,T5,T6 complete → T8 → T9
  T7,T8 complete    → T10 → T11
```

**Parallelism constraint:** `T7` é unit (parallel-safe na matriz de TESTING.md) e não
compartilha estado com T4–T6. T4–T6 editam o mesmo arquivo e não são paralelos.

---

## Task Granularity Check

| Task | Scope | Status |
| --- | --- | --- |
| T1: Schema + ingestão de campos | 1 migração + parser/repo | ✅ Granular (coeso: mesma fonte de dados) |
| T2: Tabela de histórico + backfill | 1 tabela | ✅ Granular |
| T3: Snapshot na importação | 1 função | ✅ Granular |
| T4: Repositório estoque | 1 domínio | ✅ Granular |
| T5: Repositório transporte | 1 domínio | ✅ Granular |
| T6: Repositório fornecedores | 1 domínio | ✅ Granular |
| T7: CSV util | 1 módulo | ✅ Granular |
| T8: Rotas de página + template | 1 router + 1 template | ⚠️ OK (coeso) |
| T9: CSS + navegação | 1 arquivo CSS + link | ✅ Granular |
| T10: Rota de export | 1 endpoint | ✅ Granular |
| T11: Aceitação P1 | 1 arquivo de testes | ⚠️ OK (por grupo de critério) |

---

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| --- | --- | --- | --- |
| T1 | None | inicio Phase 1 | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T2 | T2 → T3 | ✅ Match |
| T4 | T2 | T2 → T4 | ✅ Match |
| T5 | T4 | T4 → T5 | ✅ Match |
| T6 | T5 | T5 → T6 | ✅ Match |
| T7 | None | T2 → T7 [P] (sem dep.) | ✅ Match (`[P]`, sem dep.) |
| T8 | T4, T5, T6 | T6 → T8 | ✅ Match |
| T9 | T8 | T8 → T9 | ✅ Match |
| T10 | T7, T8 | T7,T8 → T10 | ✅ Match |
| T11 | T9, T10 | T10 → T11 | ✅ Match |

---

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| --- | --- | --- | --- | --- |
| T1 | DB models/migrations + ingestion parser | integration + unit | integration + unit | ✅ OK |
| T2 | DB models/migrations | integration | integration | ✅ OK |
| T3 | repositories | integration | integration | ✅ OK |
| T4 | repositories | integration | integration | ✅ OK |
| T5 | repositories | integration | integration | ✅ OK |
| T6 | repositories | integration | integration | ✅ OK |
| T7 | web util (CSV) | unit | unit | ✅ OK |
| T8 | web rotas | integration | integration | ✅ OK |
| T9 | web static/templates | integration | integration | ✅ OK |
| T10 | web rotas | integration | integration | ✅ OK |
| T11 | fluxos de aceitação | e2e | e2e | ✅ OK |

Nenhum `Tests: none`; nenhuma task deixa camada sem verificação.

---

## Follow-ups do code review (PR #66) — 2026-09-30

Veredito: **pode mergear** (0 Critical, 0 Important). Minors não bloqueantes registrados
para uma task de folga futura:

- **FU-1** `web/relatorios.py:26` — `_inicio`/`_fim` importados (privados) de `web/kpis.py`,
  criando a 3ª cópia do recorte UTC (`web/correcoes.py` tem o par). Extrair para `web/periodo.py`.
  ✅ **Resolvido** em `web/periodo.py` (`inicio_do_dia`/`fim_do_dia`), reusado por
  `kpis.py`/`correcoes.py`/`relatorios.py`; testes em `tests/web/test_periodo.py`.
- **FU-2** `alembic/versions/c4a81f0d9e2b_relatorios_historico.py:88,94,102` — backfill usa
  `CURRENT_TIMESTAMP` (naive/segundos) vs. linhas vivas `_agora` (aware/microssegundos); alinhar
  com bind param `datetime.now(UTC)`. ✅ **Resolvido**: `_backfill` usa `:agora` =
  `datetime.now(UTC)`; teste `test_backfill_historico_dos_catalogos` valida os 3 domínios
  com `.ffffff` e janela temporal (2026-10-02).
- **FU-3** `alembic/versions/c4a81f0d9e2b_relatorios_historico.py:27-79` — `upgrade()` ~53 linhas
  (teto 50); extrair o bloco `create_table`/índices. ✅ **Resolvido**: extraído para
  `_criar_tabela_historico()`; `alembic/` formatado (black/ruff) e incluído no gate
  (CI, Makefile, pre-commit) — 2026-10-06.
- **FU-4** `tests/acceptance/test_relatorios_{estoque,transporte}.py` — anotar `quando: datetime`.
  ✅ **Resolvido** nos dois arquivos (2026-10-06).
- **FU-5** `tests/web/test_relatorios.py` — cobrir 422 de data mal-formada também na rota de export
  (`REL-35`). ✅ **Resolvido** com `test_export_data_invalida_422` (2026-10-02).
- **FU-6** `src/gestlog/web/relatorios.py:217` / `tests/web/test_relatorios.py` — o
  `_validar_periodo(desde, ate)` da rota de exportação não é exercitado (`test_periodo_invalido_422`
  cobre só a página); se a linha fosse removida, nenhum teste falharia. Registrar 422 `de > ate`
  no export (`REL-34`). ✅ **Resolvido** com `test_export_periodo_invalido_422` (2026-10-06).
- **FU-7** `alembic/script.py.mako` — o template de autogeração emite código fora do padrão
  (aspas simples via `repr`, linha `${imports}` em branco, `typing` antigo), então toda migração
  nova nasce violando o gate recém-incluído. Alternativa mínima já documentada (`make format` após
  `alembic revision`, em `AGENTS.md` Gotchas). Alinhar o template é opcional. LOW do review do
  PR #71 (2026-10-06).
