# F2 — HITL: escrita com aprovação — Tasks

**Design**: `docs/specs/features/f2-hitl/design.md`
**Spec**: `docs/specs/features/f2-hitl/spec.md`
**Status**: In progress
**Progresso**: T1 ✅ · T2 ✅ · T3 ✅ · T4 ✅ · T5 ✅ · T6 ✅ · T7 ✅ · T8 ✅ · T9 ✅ · T10 ✅ · T11–T12 pendentes

---

## Execution Plan

### Phase 0 — Modelo & migração (sequential)

```
T1
```

### Phase 1 — Persistência (sequential)

```
T1 → T2
```

### Phase 2 — Domínio (sequential)

```
T1 ─┬→ T3 ─┐
    └→ T2 ─┴→ T4 → T5
```

### Phase 3 — Decisão & escrita (sequential)

```
T1 → T6 ─┐
T5 ──────┴→ T7 → T8
```

### Phase 4 — Retenção (sequential)

```
T7 → T9
```

### Phase 5 — Web (sequential)

```
T5,T7,T8 → T10 → T11
```

### Phase 6 — Testes de aceitação (sequential)

```
T1..T11 → T12
```

---

## Task Breakdown

### T1: Modelo `ItemCorrecao` + migration

**What**: Adicionar a entidade `ItemCorrecao` (`item_correcao`) com os campos do
design (tipo, alvo_chave, campo, valor_no_pedido, valor_sugerido, justificativa,
fonte, status, decisão e aplicação), `empresa_id` FK e índices
`(empresa_id,status)`/`(empresa_id,tipo,alvo_chave,campo)`. Gerar a nova revision
Alembic após `5f1c4d61cc86`, válida para SQLite e Postgres.
**Where**: `src/gestlog/db/models.py` (modify), `alembic/versions/<nova>.py` (new)
**Depends on**: None · **Reuses**: `Base`, padrão da migration inicial
**Requirement**: APR-01, ESC-01, EDG-10 · **Tests**: integration · **Gate**: quick
**Done when**: `alembic upgrade head` cria a tabela; `alembic downgrade base` volta;
`tests/test_migrations.py` cobre a nova revision.

### T2: `CorrectionRepository` com escopo de empresa

**What**: Repositório da fila com `list_by_status`, `existe_para`, `abertos_para`,
`listar_trilha(desde, ate, limite)` e `purgar_expiradas`; reexportar em
`repositories/__init__.py`.
**Where**: `src/gestlog/repositories/correcoes.py` (new),
`src/gestlog/repositories/__init__.py` (modify)
**Depends on**: T1 · **Reuses**: `EmpresaScopedRepository`
**Requirement**: INC-03, APR-06, ESC-05, TRA-01/02 · **Tests**: integration
**Gate**: quick
**Done when**: nenhuma leitura sem filtro de empresa; teste de isolamento entre 2
tenants passa; purga remove só itens decididos.

### T3: Regras de completude por tipo

**What**: `campos_faltantes(tipo, registro)` e `valor_atual(tipo, registro, campo)`
com a tabela explícita do design (vazio/zero/default como ausente), deixando
`quantidade`/`ativo`/identidades fora.
**Where**: `src/gestlog/correcoes/__init__.py` (new),
`src/gestlog/correcoes/completude.py` (new)
**Depends on**: T1 · **Reuses**: `db.models` (StockItem/Supplier/TransportRecord)
**Requirement**: INC-01/02, SUG-01 · **Tests**: unit · **Gate**: quick
**Done when**: testes por tipo (vazio, zero, valor legítimo zero) passam; os
catálogos usados no teste cobrem os 3 tipos.

### T4: Geração determinística de sugestões

**What**: `sugerir(tipo, campo, registro, contexto)` com as estratégias do design
(mais frequente / mediana / média), `Sugestao(campo, valor, justificativa, fonte)`,
`valor=None` quando não há base; desempate determinístico.
**Where**: `src/gestlog/correcoes/sugestoes.py` (new)
**Depends on**: T2, T3 · **Reuses**: repositórios dos catálogos do tenant
**Requirement**: SUG-01..05 · **Tests**: unit · **Gate**: quick
**Done when**: caso com base gera valor+justificativa+fonte; caso sem base gera
`valor=None`; dois dados iguais no tenant produzem o mesmo resultado.

### T5: Serviço de fila — materialização idempotente

**What**: `CorrectionService` com `gerar_fila()` (dedup por `valor_no_pedido`) e
`listar(status)`; usa completude + sugestões + repositório. Não depende do grafo.
**Where**: `src/gestlog/correcoes/servico.py` (new)
**Depends on**: T2, T4 · **Reuses**: `CorrectionRepository`, catálogos
**Requirement**: INC-01/02/04, SUG-04, APR-01, EDG-01/06/07/08 · **Tests**: unit +
integration · **Gate**: quick
**Done when**: chamar `gerar_fila()` duas vezes não duplica pendentes; um item por
campo faltante; fila vazia e tenant sem dados são tratados.

### T6: Eventos de auditoria de correção

**What**: Adicionar `EVENTO_CORRECAO_APROVADA/REJEITADA/APLICADA/FALHOU` a
`EVENTOS`; documentar os call sites e o `detalhe` sem texto livre.
**Where**: `src/gestlog/audit/eventos.py` (modify)
**Depends on**: T1 · **Reuses**: `registrar_evento`, `AuditRepository`
**Requirement**: ESC-02, ESC-06 · **Tests**: unit · **Gate**: quick
**Done when**: evento desconhecido segue levantando; os 4 eventos são aceitos e
registrados sem commit.

### T7: Aprovação — decisão, aplicação e auditoria

**What**: `CorrectionService.aprovar(item_id, user_id, papel)` com 404 cross-tenant,
409 terminal/sem-sugestão, re-checagem do alvo, detecção de conflito por
`valor_no_pedido`, no-op quando sugerido = atual, `upsert` do catálogo e auditoria
na mesma transação; falha → rollback + `falhou`.
**Where**: `src/gestlog/correcoes/servico.py` (modify)
**Depends on**: T5, T6 · **Reuses**: `upsert` dos catálogos, `registrar_evento`
**Requirement**: APR-02/04/05, ESC-01..06, EDG-02/03/04/05/09 · **Tests**:
integration · **Gate**: quick
**Done when**: aprovar atualiza o registro e grava `correcao_aplicada` com autor e
timestamp; conflito/alvo ausente/erro marcam `falhou` sem escrita parcial; item
terminal recusa (409); aprovar sem sugestão recusa (409).

### T8: Rejeição com justificativa

**What**: `CorrectionService.rejeitar(item_id, user_id, papel, justificativa)` com
justificativa obrigatória (422), 404/409 e auditoria `correcao_rejeitada`.
**Where**: `src/gestlog/correcoes/servico.py` (modify)
**Depends on**: T7 · **Reuses**: T5/T7
**Requirement**: APR-03/04/05 · **Tests**: integration · **Gate**: quick
**Done when**: rejeitar sem justificativa é recusado; com justificativa grava
`rejeitado` + autoria + auditoria; re-decidir recusa.

### T9: Retenção inclui `item_correcao`

**What**: Ligar `CorrectionRepository.purgar_expiradas` ao
`audit.retencao.purgar_expiradas`, somando ao total; manter `AuditLog` não purgado.
**Where**: `src/gestlog/audit/retencao.py` (modify)
**Depends on**: T7 · **Reuses**: `retencao_dias`, `EmpresaRepository.list_all`
**Requirement**: EDG-10 · **Tests**: integration · **Gate**: quick
**Done when**: itens decididos além do prazo são removidos; pendentes permanecem;
`tests/audit/test_auditoria.py` cobre a nova tabela.

### T10: Web — fila e decisão (HTML PRG)

**What**: Router `create_correcoes_router()` com `GET /correcoes` (gera e lista
pendentes, agrupados, estado vazio, paginação), `POST /correcoes/{id}/decisao`
(`form`, `DecisaoCorrecao`, PRG 303, 403/404/409/422 re-renderizados); schema
`DecisaoCorrecao`; entrada de navegação `admin`/`gestor`; registrar no app.
**Where**: `src/gestlog/web/correcoes.py` (new),
`src/gestlog/web/schemas.py` (modify), `src/gestlog/web/app.py` (modify),
`src/gestlog/web/templates/{base,correcoes}.html` (modify/new)
**Depends on**: T5, T7, T8 · **Reuses**: `get_sync_session`, `exigir_papel`,
`get_current_empresa`, padrão PRG/`Form()` (L-009)
**Requirement**: INC-01..05, APR-01..04, EDG-08/09 · **Tests**: integration
**Gate**: quick
**Done when**: a fila aparece só com itens do tenant; `operador` recebe 403; aprovar
redireciona (303) e o item sai da fila; cross-tenant 404; sem sessão → login.

### T11: Web — trilha de ações (P2)

**What**: `GET /correcoes/historico` com filtro `desde`/`ate`, listando
registro/campo/valor/autor/timestamp do tenant e estado vazio.
**Where**: `src/gestlog/web/correcoes.py` (modify),
`src/gestlog/web/templates/correcoes_historico.html` (new)
**Depends on**: T10 · **Reuses**: `CorrectionRepository.listar_trilha`, padrão de
`web/kpis.py` para datas
**Requirement**: TRA-01/02/03 · **Tests**: integration · **Gate**: quick
**Done when**: duas correções aparecem na trilha; filtro de período respeitado;
isolamento por tenant confirmado.

### T12: Testes de aceitação F2 + ajuste das suítes existentes

**What**: Arquivo de aceitação cobrindo os critérios P1/P2 (INC, SUG, APR, ESC,
TRA, EDG) ponta a ponta com dois tenants e modelo fake; atualizar as suítes que
afirmam contratos afetados: migration, auditoria/purga, conjunto read-only das tools
(AD-002) e eventos exatos do turno de chat.
**Where**: `tests/acceptance/test_f2_hitl.py` (new),
`tests/test_migrations.py`, `tests/audit/test_auditoria.py`,
`tests/test_repositories.py`, `tests/agents/test_specialists.py`,
`tests/test_tools.py`, `tests/copilot/test_service.py`, `tests/acceptance/test_f1_mvp.py`
**Depends on**: T1..T11 · **Reuses**: `conftest` (DB em memória, `fake_model_cls`)
**Requirement**: todos · **Tests**: e2e · **Gate**: full
**Done when**: cada critério tem um teste; read-only do chat permanece provado (sem
tool de escrita vinculada); suíte completa verde com cobertura ≥ 80%.

---

## Parallel Execution Map

```
Phase 0:  T1
Phase 1:  T1 → T2
Phase 2:  T1 → T3 ; T2 → T4 (T2,T3) → T5
Phase 3:  T1 → T6 ; T5,T6 → T7 → T8
Phase 4:  T7 → T9
Phase 5:  T10 (T5,T7,T8) → T11
Phase 6:  T12 (todos)
```

**Constraint**: quase todas as tasks tocam DB/TestClient, portanto são **não
parallel-safe** (TESTING.md); executar sequencialmente por fase.

---

## Task Granularity Check

| Task | Scope | Status |
| --- | --- | --- |
| T1 modelo+migration | 2 artefatos coesos | ✅ |
| T2 repositório | 1 módulo | ✅ |
| T3 completude | 1 módulo | ✅ |
| T4 sugestões | 1 módulo | ✅ |
| T5 serviço de fila | 1 serviço | ✅ |
| T6 eventos | 1 módulo | ✅ |
| T7 aprovar/aplicar | 1 fluxo | ✅ |
| T8 rejeitar | 1 fluxo | ✅ |
| T9 retenção | 1 integração | ✅ |
| T10 web fila/decisão | 1 router + UI | ✅ |
| T11 web trilha | 1 página | ⏳ |
| T12 aceitação + ajustes | 1 arquivo + ajustes | ⏳ |

## Diagram-Definition Cross-Check

| Task | Depends (body) | Diagram | Status |
| --- | --- | --- | --- |
| T2 | T1 | T1→T2 | ✅ |
| T3 | T1 | T1→T3 | ✅ |
| T4 | T2,T3 | T2,T3→T4 | ✅ |
| T5 | T2,T4 | T2,T4→T5 | ✅ |
| T6 | T1 | T1→T6 | ✅ |
| T7 | T5,T6 | T5,T6→T7 | ✅ |
| T8 | T7 | T7→T8 | ✅ |
| T9 | T7 | T7→T9 | ✅ |
| T10 | T5,T7,T8 | →T10 | ✅ |
| T11 | T10 | T10→T11 | ✅ |
| T12 | T1..T11 | →T12 | ✅ |

## Test Co-location Validation

| Task | Layer created | Matrix requires | Task says | Status |
| --- | --- | --- | --- | --- |
| T1 | models/migration | integration | integration | ✅ |
| T2 | repositories | integration | integration | ✅ |
| T3 | domain (completude) | unit | unit | ✅ |
| T4 | domain (sugestões) | unit | unit | ✅ |
| T5 | service/repo | integration | unit+integration | ✅ |
| T6 | audit | unit | unit | ✅ |
| T7 | service/apply | integration | integration | ✅ |
| T8 | service/decide | integration | integration | ✅ |
| T9 | audit/repo | integration | integration | ✅ |
| T10 | web | integration | integration | ✅ |
| T11 | web | integration | integration | ✅ |
| T12 | acceptance | e2e | e2e | ✅ |

---

## Open Decisions Before Execution

- Fechar as 7 decisões de design listadas em `design.md` §"Decisões de design para
  revisão" (dedup, item sem sugestão, campos não verificados, apply síncrono,
  trilha, `detalhe` de auditoria, concorrência).
- Confirmar o rabbit hole da trilha P2 vs. `AuditLog` (retenção pode remover o item
  antes do log).
