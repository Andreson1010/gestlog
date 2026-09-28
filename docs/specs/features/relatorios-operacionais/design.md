# Relatórios operacionais por domínio — Design

**Spec:** `docs/specs/features/relatorios-operacionais/spec.md`
**Status:** Awaiting human approval
**TLC scope:** complex

---

## Architecture Overview

A feature segue o padrão do dashboard `/kpis` (AD-028) e adiciona três camadas novas:
um **histórico versionado** (`catalogo_historico`) populado na importação, um
**repositório de relatórios** que agrega sobre esse histórico, e **rotas web** de página e
exportação. O acesso a SQL permanece confinado a `repositories/` (fronteira `libs`), e as
rotas vivem em `apps` (`web/`).

```
CSV de importação
      │  ingestion/ (parser + serviço)
      ▼
 catálogos (stock_item, supplier, transport_record)   ← upsert do estado atual
      │  snapshot por registro aceito
      ▼
 catalogo_historico (empresa, dominio, chave, importado_em, payload)
      │  SELECT último snapshot/chave no período
      ▼
 repositories/relatorios.py  ──►  web/relatorios.py  ──►  relatorios.html
                                        │
                                        └──► web/csv_relatorios.py  ──►  Response CSV
```

```mermaid
flowchart LR
    U[Gestor/Admin] -->|GET /relatorios/{dominio}| R[web/relatorios.py]
    U -->|GET /relatorios/{dominio}/exportar| R
    R -->|guard admin/gestor| G[auth.exigir_papel]
    R -->|desde/ate UTC| RR[repositories/relatorios.py]
    RR -->|GROUP BY / último por chave| H[(catalogo_historico)]
    R -->|linhas| T[relatorios.html]
    R -->|linhas| C[web/csv_relatorios.py]
    C -->|utf-8-sig, ;| OUT[Response text/csv]
    I[ingestion/servico.py] -->|snapshot| H
    I --> CAT[(catálogos)]
    M[alembic revision] -.->|backfill| H
```

---

## Code Reuse Analysis

### Existing Components to Leverage

| Component | Location | How to Use |
| --- | --- | --- |
| Padrão de dashboard `/kpis` | `src/gestlog/web/kpis.py` | Mesmo guard, conversão `_inicio`/`_fim`, `Jinja2Templates`, `get_sync_session` |
| `KpiRepository` | `src/gestlog/repositories/kpis.py` | Padrão de `dataclass(frozen=True)` + `GROUP BY` + filtro `empresa_id` |
| `EmpresaScopedRepository` | `src/gestlog/repositories/base.py` | Base de repositórios com escopo de empresa |
| `_periodo` helper | `src/gestlog/repositories/kpis.py` | Reusar a ideia de limites inclusivos (avaliar extrair para `base`/módulo comum sem duplicar) |
| `exigir_papel` | `src/gestlog/auth/deps.py` | Guard admin/gestor (401 sem sessão, 403 operador) |
| `get_sync_session` | `src/gestlog/web/ingestion_ui.py` | Sessão síncrona por request |
| `importar` / `_aplicar_registros` | `src/gestlog/ingestion/servico.py` | Ponto de inserção dos snapshots |
| `upsert` dos catálogos | `src/gestlog/repositories/catalog.py` | Estender com campos novos |
| `ler_tabela` / validadores | `src/gestlog/ingestion/parser.py` | Estender com `categoria`/datas |
| Tabela HTML | `src/gestlog/web/templates/historico.html` | Referência visual de `.painel-tabela`/`.tabela-historico` |
| Migrações Alembic | `alembic/versions/*` | Nova revision com `down_revision = 9c2f7a41b6d3` |
| `tests/web/test_kpis.py` | `tests/web/test_kpis.py` | Molde de fixtures (engines sync+async, overrides, login) |

### Integration Points

| System | Integration Method |
| --- | --- |
| Importação | `ingestion/servico.py` grava snapshots após cada upsert aceito |
| Banco | Nova tabela + colunas via Alembic; acesso só via `repositories/` |
| Auth/tenancy | `exigir_papel(*PAPEIS_APROVADORES)`; empresa do `Membership` |
| App factory | `web/app.py` registra `create_relatorios_router()`; `web/__init__.py` reexporta |

---

## Components

### `CatalogoHistorico` (modelo)

- **Purpose**: snapshot versionado de cada registro de catálogo por importação.
- **Location**: `src/gestlog/db/models.py`
- **Interfaces**: colunas definidas em `spec.md` (Data Model Changes).
- **Dependencies**: `empresa` (FK), `import_job` (FK nullable).
- **Reuses**: convenções de `DateTime(timezone=True)`, `Uuid`, `Index`.

### `HistoricoRepository`

- **Purpose**: escrever snapshots na importação e ler a versão vigente por chave/período.
- **Location**: `src/gestlog/repositories/historico.py` (novo)
- **Interfaces**:
  - `registrar(job: ImportJob, dominio: str, chave: str, **payload) -> CatalogoHistorico` — grava 1 snapshot.
  - `ultimo_por_chave(empresa_id, dominio, desde, ate) -> Select[CatalogoHistorico]` — subconsulta do último `importado_em` por `chave` no período (base para agregações).
- **Dependencies**: `Session`.
- **Reuses**: `EmpresaScopedRepository`/`_periodo` (semântica inclusiva).
- **Nota de granularidade**: se a leitura crescer, extrair a subconsulta para função
  privada; manter arquivo ≤ 800 linhas.

### `RelatorioRepository`

- **Purpose**: agregar dados do histórico por domínio e período.
- **Location**: `src/gestlog/repositories/relatorios.py` (novo; pode crescer para módulo
  `relatorios/` por domínio se passar de 800 linhas)
- **Interfaces** (dataclasses frozen em português):
  - `estoque(empresa_id, desde, ate) -> RelatorioEstoque`
  - `transporte(empresa_id, desde, ate) -> RelatorioTransporte`
  - `fornecedores(empresa_id, desde, ate) -> RelatorioFornecedores`
- **Dataclasses**:
  - `ItemEstoque(chave, nome, categoria, local, quantidade, minimo)` + `situacao` (property).
  - `ResumoEstoque(itens, abaixo_minimo, excedentes, por_local, por_categoria)`.
  - `RegistroTransporte(...)` + `situacao`; `ResumoTransporte(registros, por_status, peso_por_rota, atrasos)`.
  - `Fornecedor(...)`; `ResumoFornecedores(fornecedores, ativos, inativos, avaliacao_media, prazo_medio, por_categoria)`.
- **Dependencies**: `Session`, `HistoricoRepository`.
- **Reuses**: padrão `dataclass(frozen=True)` + `select(...).group_by(...)` de `kpis.py`.

### `web/relatorios.py`

- **Purpose**: rotas de página e exportação, com guard, validação de período e render.
- **Location**: `src/gestlog/web/relatorios.py` (novo)
- **Interfaces**:
  - `create_relatorios_router() -> APIRouter`
  - `_inicio(valor)` / `_fim(valor)` — limites UTC inclusivos (mesma lógica de `kpis.py`).
  - `_validar_periodo(desde, ate) -> None` — levanta `HTTPException(422)` quando `de > ate`.
- **Dependencies**: `RelatorioRepository`, `exigir_papel`, `get_sync_session`, `Jinja2Templates`.
- **Reuses**: `web/kpis.py` como molde.

### `web/csv_relatorios.py`

- **Purpose**: serializar a tabela principal em CSV com `;`, BOM, escape e neutralização.
- **Location**: `src/gestlog/web/csv_relatorios.py` (novo)
- **Interfaces**:
  - `nome_arquivo(dominio, desde, ate) -> str`
  - `gerar_csv(cabecalho: Sequence[str], linhas: Iterable[Sequence[object]]) -> bytes`
  - `neutralizar(valor: str) -> str`
- **Dependencies**: `csv`, `io` (stdlib).
- **Reuses**: nada externo.

### `relatorios.html` + `relatorios.css`

- **Purpose**: render do form de período, tabela principal e blocos de agregação; estilos.
- **Location**: `src/gestlog/web/templates/relatorios.html`, `src/gestlog/web/static/relatorios.css`.
- **Reuses**: `base.html`, classes `.pagina`, `.form-periodo`, `.painel-tabela`, `.chip`.

---

## Data Models

### População do histórico na importação (REL-05)

Fluxo em `servico.importar` (conceitual):

```
job = jobs.create_job(...)              # created_at já preenchido (flush)
for registro in resultado.registros:    # apenas aceitos
    _aplicar_<dominio>(repo, empresa_id, registro)   # upsert no catálogo
    historico.registrar(job, dominio, chave, **payload_normalizado)
```

- `payload_normalizado` só contém os campos do domínio; os demais ficam nulos.
- `importado_em = job.created_at` (UTC), garantindo que a importação seja a versão corrente.
- Linhas rejeitadas não geram snapshot.

### Consulta por período — SQL conceitual (REL-20..22, REL-36)

Último snapshot por chave no período (subconsulta agrupada, sem N+1):

```sql
WITH mais_recente AS (
  SELECT chave, MAX(importado_em) AS em
  FROM catalogo_historico
  WHERE empresa_id = :empresa AND dominio = :dominio
    AND (:desde IS NULL OR importado_em >= :desde)
    AND (:ate   IS NULL OR importado_em <= :ate)
  GROUP BY chave
)
SELECT h.*
FROM catalogo_historico h
JOIN mais_recente m ON m.chave = h.chave AND m.em = h.importado_em
WHERE h.empresa_id = :empresa AND h.dominio = :dominio
  AND (:desde IS NULL OR h.importado_em >= :desde)
  AND (:ate   IS NULL OR h.importado_em <= :ate);
```

- **Sem período** → todos os snapshots entram na subconsulta; o `MAX` por chave devolve o
  estado mais recente (equivalente a "todo o histórico disponível" agregado por registro).
- **Empates de `importado_em`** na mesma chave: aceitos como não determinísticos
  (mesmo padrão de AD-028); se necessário, desempatar por `importado_em, id`.
- A partir das linhas vigentes, as agregações por domínio usam `GROUP BY`:

| Domínio | Agregação | SQL conceitual |
| --- | --- | --- |
| estoque | por local | `GROUP BY local` |
| estoque | por categoria | `GROUP BY categoria` |
| transporte | por status | `GROUP BY status` |
| transporte | peso por rota | `GROUP BY origem, destino` (`SUM(peso_kg)`, inclui 0) |
| fornecedores | ativo/inativo | `GROUP BY ativo` |
| fornecedores | indicadores | `AVG(avaliacao)`, `AVG(prazo_dias)` |
| fornecedores | por categoria | `GROUP BY categoria` |

### Regras de negócio derivadas

| Regra | Cálculo | Fonte |
| --- | --- | --- |
| Abaixo do mínimo | `quantidade < minimo` | Enunciado |
| Excedente | `minimo > 0 and quantidade > minimo * 2` | Q2 + `tools/inventory.py` (`_FATOR_EXCEDENTE = 2`) |
| Atraso | `data_entrega > previsao_entrega` (ambos não nulos) | Q3 |
| Rota | par `(origem, destino)` | Q4 |
| Indicadores fornecedor | `AVG(avaliacao)`, `AVG(prazo_dias)` | Q5 |

---

## Error Handling Strategy

| Error Scenario | Handling | User Impact |
| --- | --- | --- |
| Sem sessão (página/export) | `current_active_user` → 401 | JSON 401 |
| Papel não autorizado | `exigir_papel` → 403 | JSON 403 |
| `de > ate` | `_validar_periodo` → `HTTPException(422)` | JSON 422 |
| Data inválida (`de=abc`) | FastAPI valida `date` → 422 | JSON 422 |
| `{dominio}` desconhecido | rota não cadastrada / 404 explícito | JSON 404 |
| Empresa sem registros | resumo vazio + template com estado vazio; CSV header-only 200 | Tela vazia sem erro |
| Campo de texto hostil no CSV | escape RFC 4180 + neutralização `'` | CSV seguro ao abrir |

---

## Tech Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| Fonte do relatório | tabela `catalogo_historico` (versionada) | Q6: permite estado real no período; catálogo só guarda o último upsert |
| Granularidade do snapshot | 1 linha por registro aceito/importação | Preserva valores no tempo sem duplicar por campo |
| `data_entrega` | adicionada junto de `previsao_entrega` | Necessária para Q3 ("entregue após a previsão") |
| Deduplicação | último snapshot por `chave` no período | Evita repetir o mesmo SKU/fornecedor/rastreio no relatório |
| Backfill | `INSERT ... SELECT` na migração, `import_job_id=NULL` | Dados pré-migração continuam visíveis; não polui o histórico de importação |
| CSV | `csv` stdlib, `;`, `utf-8-sig` | Q7/Q11; sem dependência nova (AD-007/constraint de stack) |
| Legibilidade CSV | exporta a tabela principal (coluna `Situação`) | Coerente com Q12 (empresa vazia → só cabeçalho) |
| CSS | arquivo `relatorios.css` separado | `app.css` já em 802 linhas (teto 800 do AGENTS.md) |
| Validação de período | `HTTPException(422)` explícita | Q9; distingue do 422 do framework sem alterar UX |
| Sessão/guard | reusar `/kpis` | Consistência e menor risco |

---

## Mitigação dos riscos (CONCERNS/AGENTS)

- **Multi-tenancy**: toda leitura parte de `empresa_id` do `Membership`; o router não aceita
  `empresa_id` do cliente; testes com dois tenants.
- **Timezone**: `_inicio`/`_fim` idênticos aos de `kpis.py`; `importado_em` em UTC.
- **N+1**: subconsulta agrupada + `GROUP BY`; nenhuma agregação em laço por registro.
- **Tetos de código**: repositório pode virar pacote `repositories/relatorios/` por domínio
  se exceder 800 linhas; funções ≤ 50 linhas.
- **Fronteira de dependência**: SQL só em `repositories/`; `web/` não escreve query.
- **Regressão de shell**: link de nav aditivo, visível só a admin/gestor; manter
  `tests/web/test_shell.py` e `tests/web/test_app.py` verdes.
