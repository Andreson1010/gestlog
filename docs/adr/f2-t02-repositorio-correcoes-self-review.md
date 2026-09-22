# ADR: f2-t02-repositorio-correcoes

## 1. Contexto & Objetivo

A T2 entrega a camada de persistência da fila HITL da F2: o `CorrectionRepository`
(`src/gestlog/repositories/correcoes.py`), sua reexportação em
`repositories/__init__.py` e os testes de integração em
`tests/test_repositories_correcoes.py`. Ela fica entre o modelo `ItemCorrecao` (T1)
e o serviço de fila/decisão/aplicação (T5–T8) e é a **única** porta de SQL para a
tabela `item_correcao`.

O desafio não é o CRUD em si, e sim concentrar todas as consultas que o épico exige
— listar por status, checar dedup, buscar itens abertos, montar a trilha P2 e
purgar por retenção — **sem que nenhuma leitura escape do escopo de empresa**. O
`EmpresaScopedRepository` já dá `get`/`list`/`add` filtrados; o trabalho da T2 é
acrescentar as consultas específicas mantendo essa mesma régua de tenancy,
determinismo de ordenação e recortes de status explícitos.

## 2. Decisões Arquiteturais

- **Todas as consultas nascem e permanecem escopadas por `empresa_id`, incluindo
  as de dedup e a purga.**
  - **Justificativa:** o risco de tenancy da F2 não é só "não listar de outro
    tenant"; é a **dedup** (`existe_para`/`abertos_para`) e a **purga**. Se a dedup
    enxergasse itens de outro tenant, a materialização da fila (T5) suprimiria um
    item legítimo; se a purga não filtrasse empresa, apagaria filas alheias. Por
    isso cada `where` começa por `ItemCorrecao.empresa_id == empresa_id`, e o teste
    de isolamento (`test_correcoes_isoladas_por_empresa`) exercita leitura, dedup,
    trilha e `get` cross-tenant com dois tenants.

- **A dedup é servida por duas consultas com propósitos distintos, não por uma
  consulta genérica de "já existe".**
  - **Justificativa:** as regras de materialização do design (rules de
    `gerar_fila`) têm dois critérios independentes: (1) existe item **aberto**
    (`pendente`/`aprovado`) para a chave → não cria, independentemente do valor; e
    (2) existe item **terminal** com o **mesmo `valor_no_pedido`** → não cria. Isso
    mapeia em `abertos_para` (sem filtro de valor, devolve a lista para o serviço
    decidir) e `existe_para` (com o valor, resolve o snapshot "sticky"). Fundir as
    duas numa só API forçaria o serviço a reinterpretar a presença de linhas ou o
    repositório a receber a regra de negócio. Manter as duas consultas separadas
    deixa o repositório somente-SQL e a regra de idempotência no serviço (T5).

- **A purga remove apenas os estados terminais e o filtro de status é uma
  *allow-list*, nunca uma *deny-list*.**
  - **Justificativa:** `purgar_expiradas` usa `_STATUS_TERMINAIS`
    (`rejeitado`/`aplicado`/`falhou`) — exatamente os terminais do design. Um item
    `pendente`/`aprovado` é trabalho operacional em curso e nunca pode sumir por
    retenção (EDG-10), então a consulta autoriza o que apaga em vez de excluir o
    que preserva. Resultado: um status novo e não mapeado jamais seria apagado por
    engano. A purga segue a forma do `ConversationRepository.purgar_expiradas`
    (seleciona ids → `delete ... in_` → devolve a contagem), com a diferença de que
    aqui não há dependentes em cascata.

- **A trilha P2 (`listar_trilha`) filtra `aplicado`/`falhou` — o recorte de
  **escrita**, não o conjunto terminal do design.**
  - **Justificativa:** a P2 pede o "histórico de **correções aplicadas**"
    (spec P2, TRA-01: registro/campo/valor/autor/timestamp). `rejeitado` é
    terminal para a máquina de estados (não pode ser re-decidido), mas **não gerou
    escrita**; incluí-lo numa trilha de correções aplicadas mostraria uma ação que
    nunca tocou o catálogo. A distinção ficou explícita em duas constantes com
    nomes honestos — `_STATUS_TERMINAIS` (design) e `_STATUS_TRILHA` (recorte de
    escrita) — e o docstring do método explica por que divergem. Um teste dedicado
    (`test_listar_trilha_ignora_rejeitado`) fixa o recorte para que a T11 não o
    mude em silêncio.

- **Ordenação determinística e filtro de período inclusivo sobre colunas
  *timezone-aware*.**
  - **Justificativa:** toda leitura ordena por uma chave estável mais `id` como
    desempate (`created_at, id` nas listas; `decidido_em.desc(), id` na trilha),
    para que paginação e testes sejam reprodutíveis mesmo com timestamps
    empatados. `decidido_em`/`created_at` são `DateTime(timezone=True)` (T1), e o
    filtro da trilha usa `>=`/`<=` (inclusivo) com `desde`/`ate` opcionais: o
    `limite` é aplicado só quando informado, sem impor um teto arbitrário fora da
    T11. A validação de que `agora` tem fuso continua na camada de retenção
    (`audit.retencao.purgar_expiradas`), que é quem produz o `limite` da purga.

- **Testes de integração num arquivo próprio, espelhando a fronteira criada.**
  - **Justificativa:** `tests/test_repositories_correcoes.py` cobre isolamento de
    tenancy, ordenação, semântica de dedup, recorte da trilha e purga seletiva
    contra SQLite em memória (sem rede/Ollama, como manda a suíte). O arquivo
    separado mantém `tests/test_repositories.py` como o agregado dos repositórios
    anteriores, coerente com a divisão por fronteira (a T12 ainda pode reafirmar o
    contrato no agregado).

## 3. Trade-offs & Compromissos

- **`purgar_expiradas` seleciona os ids antes de apagar (duas idas ao banco), em
  vez de um `DELETE` único com `rowcount`.** O shape foi mantido igual ao do
  `ConversationRepository` — que precisa dos ids para os *deletes* em cascata —
  para não introduzir um padrão paralelo de purga no mesmo módulo. O custo é
  materializar as PKs terminais da empresa; aceitável porque a purga roda por
  empresa e é idempotente, e o dia em que a tabela justificar um `DELETE` em massa
  isso vira uma otimização isolada, sem mudar o contrato (`-> int`).

- **`listar_trilha` exclui `rejeitado`.** É uma leitura defensável da P2
  ("correções aplicadas"), mas não é a única: se na T11 o produto interpretar
  "ações" de forma ampla, a rejeição com justificativa/autor também é uma ação
  auditável. O recorte está explicitamente testado justamente para que essa
  decisão seja reversível com intenção, e não por acidente.

- **`existe_para` considera qualquer status (aberto ou terminal) com o mesmo
  snapshot de valor.** Isso é redundante com `abertos_para` quando o item aberto
  tem o mesmo valor, mas é o que permite ao serviço implementar a regra 2 sem uma
  terceira consulta. Aceito por simplicidade de SQL; a composição exata das regras
  fica na T5.

- **Sem validação de status/limite de datas no repositório.** `list_by_status`
  aceita qualquer string e `listar_trilha` aceita `datetime` naive. Preservar o
  repositório como porta somente-SQL mantém a validação no serviço/web (onde há
  contexto de erro HTTP); a contrapartida é que um chamador descuidado pode
  montar filtros inconsistentes — coberto pelo uso interno da T5/T7/T11.

## 4. Limitações Conhecidas

- **Trilha vs. `AuditLog` — possível divergência sob retenção.** A purga pode
  remover o item terminal antes de a trilha P2 ser consultada, enquanto o
  `AuditLog` (não purgado, AD-022) permanece. É o *rabbit hole* já registrado na
  decisão de design 5; a T11 decide se a página usa o item ou o log como fonte
  canônica para janelas antigas.
- **`rejeitado` não aparece na trilha P2** (ver trade-off). Se TRA-01 for lido
  como "toda ação", a T11/T12 deve estender `_STATUS_TRILHA` e ajustar o teste
  `test_listar_trilha_ignora_rejeitado`.
- **Sem índice específico para a trilha.** `decidido_em` não está em nenhum índice
  de T1; a trilha sempre filtra por empresa + status (`ix_item_correcao_empresa_status`)
  antes de ordenar por `decidido_em`, então o índice composto cobre o predicado e a
  ordenação resolve em memória sobre o subconjunto. Se o volume por empresa crescer
  muito, um índice `(empresa_id, status, decidido_em)` é a evolução natural.
- **A purga corta por `created_at`, não por `decidido_em`.** Fiel ao design
  ("`created_at < limite`") e ao padrão de `ConversationRepository`; implica que um
  item gerado há muito tempo e decidido ontem é purgado assim que a retenção vence,
  o que é a política declarada, mas não "idade da decisão".
- **Sem constraint de unicidade para dedup no banco** (herdado da T1): a
  idempotência depende de `abertos_para`/`existe_para` + serviço; duas chamadas
  concorrentes de `gerar_fila` ainda poderiam criar itens duplicados (EDG-04 fica
  como *hardening* no serviço).
