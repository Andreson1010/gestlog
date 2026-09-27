# F2 — HITL: escrita com aprovação — Specification

**Path:** `docs/specs/features/f2-hitl/spec.md`
**TLC scope:** complex
**Based on story:** o copiloto passa a corrigir/completar cadastros incompletos, sempre com aprovação humana registrada (AD-002).
**Status:** Awaiting human approval

---

## Problem Statement

Na F1 o copiloto é read-only: recomenda e explica, mas não corrige nada. PMEs
importam cadastros incompletos (campos em branco ou no valor padrão) e o operador
precisa completá-los manualmente, sem apoio e sem trilha de quem mudou o quê. A
F2 deixa o copiloto **corrigir/completar cadastros** — sempre com uma decisão
humana explícita antes de qualquer escrita (AD-002) — e registra a autoria de cada
escrita.

## Goals

- [ ] O usuário enxerga os registros com campos faltantes do próprio tenant.
- [ ] Para cada campo faltante há uma sugestão de preenchimento explicada (ou a
      marcação explícita de "sem sugestão"), nunca um valor inventado.
- [ ] Toda escrita passa por aprovação humana registrada (quem aprovou, quando e
      com qual justificativa) — nenhuma escrita automática.
- [ ] Cada escrita aplicada gera trilha de auditoria por tenant.
- [ ] O isolamento por tenant é mantido em leitura, decisão e escrita.

## Out of Scope

| Feature | Reason |
| --- | --- |
| Escrita disparada pelo próprio LLM, sem aprovação | Viola AD-002 (HITL é obrigatório) |
| Demais tools de ação do inventário AD-010 (estoque, transporte, fornecedores) | F2 cobre o caminho de correção de cadastros; as demais ações ficam para incrementos seguintes |
| Envio externo de `enviar_resposta_logistica` | Decisão humana: envio externo sai da F2 |
| Correção/completude de documentos | Escopo, formato e regras ainda não definidos |
| Integrações de API em tempo real (TMS/ERP/WMS) | F3 |
| Alertas proativos / automação em background | F4 |
| Relatórios/gráficos e demais dashboards | Fora do épico HITL |
| Detecção em massa sem revisão individual | A decisão humana por item é o núcleo da história |

---

## User Stories

### P1: Listar cadastros incompletos por tenant ⭐ MVP

**User Story**: Como gestor de logística, quero ver, por tipo de cadastro, quais
registros do meu tenant têm campos faltantes, para saber o que precisa ser
corrigido.

**Why P1**: é a porta de entrada — sem visibilidade não existe fila de correção.

**Acceptance Criteria**:
1. WHEN o usuário abre a visão de cadastros incompletos THEN o sistema SHALL listar
   apenas os registros do tenant da sessão que atendem à definição de "incompleto"
   (vazio/zero/default tratados como ausente; ver design), agrupados por tipo de
   cadastro.
2. WHEN a lista é exibida THEN o sistema SHALL indicar, por registro, quais campos
   estão faltantes.
3. WHEN um registro de outro tenant é solicitado THEN o sistema SHALL negar
   (404/403) sem vazar a existência do recurso.
4. WHEN não há registros incompletos no tenant THEN o sistema SHALL exibir um
   estado vazio claro.
5. WHEN a requisição não tem sessão válida THEN o sistema SHALL redirecionar ao
   login / responder 401.

**Independent Test**: criar 2 tenants, um com registro incompleto; confirmar que a
lista mostra apenas o registro do tenant correto e os campos faltantes.

---

### P1: Sugerir valores de preenchimento ⭐ MVP

**User Story**: Como operador logístico, quero receber uma sugestão explicada para
cada campo faltante, para corrigir o cadastro sem montar o valor do zero.

**Why P1**: a sugestão é o conteúdo da correção; sem ela não há o que aprovar.

**Acceptance Criteria**:
1. WHEN um registro incompleto é analisado THEN o sistema SHALL gerar, para cada
   campo faltante, um valor sugerido com base nos dados do próprio tenant.
2. WHEN há sugestão THEN o sistema SHALL apresentar o valor sugerido, uma
   justificativa e a fonte/dado que a sustenta.
3. WHEN não há base suficiente para sugerir THEN o sistema SHALL marcar o campo
   como "sem sugestão", em vez de inventar um valor.
4. WHEN a sugestão é gerada THEN o sistema SHALL mantê-la associada ao registro e
   ao campo correspondente, de forma rastreável até a decisão.
5. WHEN a sugestão é apresentada THEN o sistema SHALL distinguir valor atual, valor
   sugerido e origem da sugestão.

**Independent Test**: dado um registro com campo faltante e dados do tenant que
permitam inferir o valor, ver a sugestão com justificativa; num caso sem base, ver
"sem sugestão".

---

### P1: Aprovar ou rejeitar com justificativa (fila HITL) ⭐ MVP

**User Story**: Como aprovador autorizado, quero aprovar ou rejeitar cada sugestão
com justificativa, para que nenhuma escrita aconteça sem uma decisão humana.

**Why P1**: é o núcleo do HITL (AD-002) — o gate que separa recomendação de escrita.

**Acceptance Criteria**:
1. WHEN uma sugestão é criada THEN o sistema SHALL apresentá-la como item pendente
   em uma fila de ações acionáveis do tenant.
2. WHEN o aprovador autorizado (`admin` ou `gestor`) aprova um item THEN o sistema
   SHALL registrar a decisão de aprovação com usuário, papel e timestamp.
3. WHEN o aprovador autorizado rejeita um item THEN o sistema SHALL exigir
   justificativa e registrar a decisão com usuário, papel e timestamp.
4. WHEN um usuário sem papel autorizado tenta aprovar ou rejeitar THEN o sistema
   SHALL negar (403) sem alterar o item.
5. WHEN um item já decidido recebe nova decisão THEN o sistema SHALL recusá-la,
   tratando o item como terminal (pendente → aprovado/rejeitado → aplicado/falhou);
   uma nova correção do mesmo campo é um item novo.
6. WHEN um item de outro tenant é acessado THEN o sistema SHALL negar sem vazar a
   existência do recurso.

**Independent Test**: aprovar um item e rejeitar outro com justificativa; ver as
decisões registradas com autor e timestamp; tentar decidir novamente e tentar
decidir sem o papel autorizado.

---

### P1: Aplicar a correção aprovada e registrar a autoria ⭐ MVP

**User Story**: Como admin da conta, quero que a correção aprovada seja aplicada ao
cadastro e que fique registrado quem aprovou, para confiar que a mudança foi
deliberada e rastreável.

**Why P1**: aprovar sem aplicar não entrega valor; a autoria é a âncora de confiança
(FR-15/SEC-02).

**Acceptance Criteria**:
1. WHEN um item é aprovado THEN o sistema SHALL aplicar o valor aprovado ao
   registro alvo, restrito ao tenant da sessão.
2. WHEN a escrita é aplicada THEN o sistema SHALL registrar auditoria por tenant
   com: ação de escrita, registro e campo afetados, valor aplicado, usuário
   aprovador e timestamp.
3. WHEN a aplicação conclui THEN o item SHALL deixar de aparecer como pendente na
   fila.
4. WHEN a aplicação falha THEN o sistema SHALL preservar o valor anterior do
   registro e sinalizar a falha, sem escrita parcial.
5. WHEN o alvo da escrita pertence a outro tenant THEN o sistema SHALL recusar a
   aplicação sem vazar a existência do recurso.
6. WHEN a auditoria de uma escrita é registrada THEN o detalhe SHALL conter apenas
   os metadados necessários, sem PII desnecessária.

**Independent Test**: aprovar um item, confirmar o registro atualizado e a entrada
de auditoria com autor e timestamp; simular uma falha de aplicação e confirmar que
o valor anterior permanece intacto.

---

### P2: Consultar a trilha de ações

**User Story**: Como gestor de logística, quero consultar o histórico de correções
aplicadas, para auditar quem mudou o quê e quando.

**Why P2**: agrega valor de conformidade, mas depende das histórias P1.

**Acceptance Criteria**:
1. WHEN o gestor consulta o histórico de escritas THEN o sistema SHALL listar as
   ações do tenant com registro, campo, valor, autor e timestamp.
2. WHEN o gestor filtra por período THEN o sistema SHALL respeitar o filtro,
   sempre dentro do tenant.
3. WHEN não há ações no período THEN o sistema SHALL exibir estado vazio.

**Independent Test**: aplicar duas correções e vê-las na trilha, filtrando por
período e confirmando o isolamento por tenant.

---

## Edge Cases

- WHEN um registro tem múltiplos campos faltantes THEN cada campo SHALL ter seu
  próprio item, com sugestão e decisão independentes (`EDG-01`).
- WHEN o registro alvo é alterado ou reimportado entre a geração da sugestão e a
  aprovação THEN o sistema SHALL detectar o conflito em vez de sobrescrever às
  cegas (`EDG-02`).
- WHEN o registro alvo deixa de existir antes da aprovação THEN o item SHALL ser
  encerrado como falha, sem escrita e com aviso (`EDG-03`).
- WHEN dois aprovadores decidem o mesmo item em paralelo THEN apenas uma decisão
  SHALL prevalecer; a outra SHALL ser recusada por estado terminal (`EDG-04`).
- WHEN a sugestão é igual ao valor atual THEN o item SHALL ser tratado sem escrita
  efetiva (`EDG-05`).
- WHEN o tenant não tem dados importados THEN a visão de incompletos SHALL
  orientar a importar antes (`EDG-06`).
- WHEN a fila está vazia THEN o sistema SHALL exibir estado vazio claro (`EDG-07`).
- WHEN o volume de registros incompletos é grande THEN a listagem SHALL permanecer
  utilizável, com paginação/limite, sem travar a interface (`EDG-08`).
- WHEN a sessão expira durante a decisão THEN o sistema SHALL redirecionar ao login
  sem aplicar a escrita (`EDG-09`).
- WHEN itens decididos/pendentes alcançam o prazo de retenção THEN o sistema SHALL
  aplicar a política de retenção da Empresa (`EDG-10`).

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| --- | --- | --- | --- |
| INC-01 | P1: Listar incompletos | Design | Pending |
| INC-02 | P1: Listar incompletos | Design | Pending |
| INC-03 | P1: Listar incompletos | Design | Pending |
| INC-04 | P1: Listar incompletos | Design | Pending |
| INC-05 | P1: Listar incompletos | Design | Pending |
| SUG-01 | P1: Sugerir valores | Design | Pending |
| SUG-02 | P1: Sugerir valores | Design | Pending |
| SUG-03 | P1: Sugerir valores | Design | Pending |
| SUG-04 | P1: Sugerir valores | Design | Pending |
| SUG-05 | P1: Sugerir valores | Design | Pending |
| APR-01 | P1: Fila HITL | Design | Pending |
| APR-02 | P1: Fila HITL | Design | Pending |
| APR-03 | P1: Fila HITL | Design | Pending |
| APR-04 | P1: Fila HITL | Design | Pending |
| APR-05 | P1: Fila HITL | Design | Pending |
| APR-06 | P1: Fila HITL | Design | Pending |
| ESC-01 | P1: Aplicar correção | Design | Pending |
| ESC-02 | P1: Aplicar correção | Design | Pending |
| ESC-03 | P1: Aplicar correção | Design | Pending |
| ESC-04 | P1: Aplicar correção | Design | Pending |
| ESC-05 | P1: Aplicar correção | Design | Pending |
| ESC-06 | P1: Aplicar correção | Design | Pending |
| EDG-01 | Edge: múltiplos campos | Design | Pending |
| EDG-02 | Edge: conflito na aprovação | Design | Pending |
| EDG-03 | Edge: alvo inexistente | Design | Pending |
| EDG-04 | Edge: decisão paralela | Design | Pending |
| EDG-05 | Edge: sugestão = valor atual | Design | Pending |
| EDG-06 | Edge: sem dados importados | Design | Pending |
| EDG-07 | Edge: fila vazia | Design | Pending |
| EDG-08 | Edge: volume grande | Design | Pending |
| EDG-09 | Edge: sessão expirada | Design | Pending |
| EDG-10 | Edge: retenção | Design | Pending |
| TRA-01 | P2: Trilha de ações | - | Pending |
| TRA-02 | P2: Trilha de ações | - | Pending |
| TRA-03 | P2: Trilha de ações | - | Pending |

**ID format:** `[FEAT]-[NUMBER]` — aqui `INC`/`SUG`/`APR`/`ESC` (P1), `EDG`
(casos-limite) e `TRA` (P2).

**Coverage:** 35 requisitos; mapeamento para tasks na fase Tasks.

---

## Data Model Changes

Uma nova entidade: **`ItemCorrecao`** (tabela `item_correcao`), por empresa,
representando um item da fila HITL (ação sugerida + decisão + estado). Detalhes de
campos, estados terminais e constraints em `design.md`. Nova migration Alembic
(uma revision após `5f1c4d61cc86`), válida para SQLite e Postgres, com
`empresa_id` FK. Nenhuma coluna nova nos catálogos existentes (`StockItem`,
`Supplier`, `TransportRecord`): "incompleto" é derivado das colunas atuais.

## Process / Background Flow

**Happy path:** o aprovador abre a fila → o serviço materializa itens pendentes
(idempotente) a partir dos cadastros incompletos e das sugestões determinísticas →
o aprovador aprova um item → o serviço registra a decisão, aplica a correção ao
registro do tenant via `upsert` existente e grava a auditoria, tudo na mesma
transação → o item sai da fila como `aplicado`.

**Failure path — conflito/alvo ausente:** na aprovação o serviço re-verifica o
registro alvo no tenant e compara o valor atual com o snapshot do pedido; se
divergiu ou sumiu, encerra o item como `falhou` (sem escrita) e sinaliza.

**Failure path — erro de escrita:** qualquer exceção na aplicação faz rollback da
escrita, preserva o valor anterior e marca o item como `falhou` numa transação
separada.

## API Changes

Novo router web (`src/gestlog/web/correcoes.py`), registrado em `web/app.py`:

- `GET /correcoes` — fila de itens pendentes (HTML, guard `admin`+`gestor`).
- `POST /correcoes/{item_id}/decisao` — `form` com `decisao` (`Literal`) e
  `justificativa`; PRG 303 no sucesso (L-009).
- `GET /correcoes/historico` — trilha de ações por período (P2, guard
  `admin`+`gestor`).

Sem envio externo; nenhum endpoint no caminho do chat (AD-002).

## Frontend Changes

Nova página de fila de correções (com entrada de navegação em `templates/base.html`
visível a `admin`/`gestor`): agrupada por tipo, exibindo valor atual, valor
sugerido, justificativa, fonte e ações de aprovar/rejeitar. Estado vazio claro
(sem itens / sem dados importados). Página de trilha (P2) com filtro por período.
O chat permanece read-only.

## Tests Required

- **Unit:** regras de completude por tipo; geração determinística de sugestões
  (com e sem base); dedup/idempotência da materialização; máquina de estados do
  item; detecção de conflito e serialização de valores.
- **Integration:** repositório com escopo de empresa (404 cross-tenant);
  aprovação aplica `upsert` + auditoria na mesma transação; rejeição exige
  justificativa; guard de papel (403); item terminal recusa re-decisão (409);
  retenção purga itens vencidos; migration sobe/desce.
- **Edge case:** conflito por reimportação; alvo inexistente; sugestão = valor
  atual (sem escrita); fila vazia; ausência de dados do tenant; paginação.
- **Acceptance/E2E:** fluxo completo listar → sugerir → aprovar → aplicar →
  auditar → trilha, com dois tenants.
- **Existing tests to update:** `tests/test_migrations.py` (nova revision),
  `tests/audit/test_auditoria.py` (purga cobre `item_correcao`),
  `tests/copilot/test_service.py` (o conjunto exato de eventos do turno de chat
  **não** muda), `tests/agents/test_specialists.py` + `tests/test_tools.py`
  (confirma que **nenhuma** tool de escrita foi adicionada ao grafo),
  `tests/acceptance/test_f1_mvp.py` (read-only continua provado),
  `tests/test_repositories.py` (`CorrectionRepository`).

## Files That Will Change

| File | Change type | Why |
| --- | --- | --- |
| `src/gestlog/db/models.py` | modify | Nova entidade `ItemCorrecao` |
| `alembic/versions/<nova>.py` | new | Tabela `item_correcao` |
| `src/gestlog/repositories/correcoes.py` | new | Repositório escopado por empresa |
| `src/gestlog/repositories/__init__.py` | modify | Reexportar o repositório |
| `src/gestlog/correcoes/{completude,sugestoes,servico}.py` | new | Domínio HITL determinístico |
| `src/gestlog/audit/eventos.py` | modify | Novos eventos de correção |
| `src/gestlog/audit/retencao.py` + `repositories/conversations.py` | modify | Purga inclui itens |
| `src/gestlog/web/correcoes.py` | new | Rotas da fila, decisão e trilha |
| `src/gestlog/web/schemas.py` | modify | `DecisaoCorrecao` |
| `src/gestlog/web/app.py` | modify | Registrar o router |
| `src/gestlog/web/templates/{base,correcoes,correcoes_historico}.html` | modify/new | Navegação e telas |
| `tests/...` | new/modify | Ver "Tests Required" |

## Risks

- **Escrita via ReAct (AD-002):** o loop executa qualquer tool vinculada
  genericamente (`agents/base.py:95-104`); qualquer tool de escrita em
  `build_*_tools` daria mutação pelo LLM. Mitigação estrutural: a escrita vive num
  serviço/rota separado, **nunca** vinculada ao grafo; teste de aceitação afirma o
  conjunto de tools read-only. *(AGENTS.md; AD-002)*
- **Tenancy na escrita:** `EmpresaScopedRepository` escopa leitura; `upsert` recebe
  `empresa_id` do closure. Todo caminho de aplicação resolve `empresa_id` da
  sessão e 404 cross-tenant. *(NFR-03; AD-018)*
- **Auditoria acoplada ao turno de chat:** `test_answer_registra_auditoria_sem_pii`
  afirma o conjunto exato de eventos do turno; os novos eventos ficam no caminho de
  aplicação, não no chat. *(SEC-02; AD-022)*
- **Retenção incompleta:** a purga hoje só percorre conversas; sem incluir
  `item_correcao`, itens e trilha ignoram a política. *(EDG-10; AD-022)*
- **Conflito de escrita às cegas:** snapshot do valor no pedido + re-checagem na
  aprovação evitam sobrescrever reimportação alheia. *(EDG-02)*
- **Valores "zero legítimos":** tratar todo `0` como ausente corromperia
  `quantidade`; os campos verificados são explícitos por tipo. *(INC-01)*
- **Free text em auditoria:** `justificativa`/`motivo_rejeicao` podem conter dado
  sensível; o `detalhe` de auditoria não os carrega, só metadados. *(ESC-06)*
- **Cross-tenant via target:** o alvo da escrita pode existir em outro tenant; a
  aplicação só resolve alvos do `empresa_id` da sessão (404). *(ESC-05)*
- **Concorrência:** duas decisões no mesmo item — a segunda encontra estado
  terminal e é recusada (409). *(EDG-04)*
- **Timezone:** timestamps com fuso; a purga exige `agora` aware (AD-022).

## Open Questions

Todas as questões abertas da história foram decididas no Checkpoint 1 (aprovador =
`admin`+`gestor`; incompleto = vazio/zero/default sobre as colunas atuais;
sugestão com payload acionável; escopo = correção interna de cadastros;
idempotência/terminalidade; retenção segue a Empresa; superfície só web/API).
Decisões de design remanescentes a confirmar estão listadas em `design.md`
§"Decisões de design para revisão".

## Success Criteria

- [ ] Um gestor vê os cadastros incompletos do próprio tenant com os campos
      faltantes, sem cruzar tenants.
- [ ] Cada campo faltante tem sugestão explicada (valor + justificativa + fonte) ou
      a marcação "sem sugestão"; nenhum valor inventado.
- [ ] Toda escrita aprovada é aplicada ao cadastro e auditada com autor, papel e
      timestamp.
- [ ] Nenhuma escrita acontece sem decisão humana: nenhuma tool de escrita é
      vinculada ao grafo (AD-002 preservado).
- [ ] Item decidido não é re-decidido; uma nova correção do mesmo campo é um item
      novo.
- [ ] Itens e trilha respeitam a retenção da Empresa (`purgar_expiradas` cobre a
      nova tabela).
