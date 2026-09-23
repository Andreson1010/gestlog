# ADR: f2-t01-modelo-item-correcao

## 1. Contexto & Objetivo

A F2 introduz o primeiro caminho de **escrita com aprovação humana** do produto: o
copiloto e o grafo LangGraph continuam estritamente *read-only* (AD-002), e uma
correção cadastral só se materializa depois que `admin` ou `gestor` aprova o que um
operador pediu. Para isso a decisão precisa **sobreviver à requisição** — quem pediu
o quê, com que valor, por quê, quem decidiu e quando —, o que exige persistência
própria, não estado em memória. A T1 é a fundação desse épico: entrega a entidade
`ItemCorrecao` (tabela `item_correcao`) e a *revision* Alembic que a cria, sem tocar
em repositório, serviço ou web (escopo estritamente de modelo + migration).

O desafio arquitetural aqui não é a tabela em si, e sim **modelar todo o ciclo de
vida de uma decisão em uma única linha sem migration de nulabilidade nos catálogos
existentes** e mantendo o esquema portátil entre SQLite (testes/dev) e Postgres
(produção). A entidade é genérica por tipo (`estoque`/`fornecedores`/`transporte`) e
por campo, então serve a dez pares `(tipo, campo)` diferentes com as mesmas colunas
— o que evita inflar o modelo a cada novo campo verificado.

## 2. Decisões de Arquitetura

- **Tabela dedicada `item_correcao` em vez de reutilizar uma estrutura existente
  (`audit_log`, `import_job`) ou sobrecarregar um catálogo.**
  - **Justificativa:** o item tem estado mutável com transições terminais
    (`pendente → aprovado → aplicado/falhou` ou `pendente → rejeitado`), autoria da
    decisão e uma trilha que o repositório vai ler por `(empresa_id, status)`. O
    `AuditLog` é *append-only* e imutável por desenho (AD-022) — reusá-lo misturaria
    conformidade com fila operacional e quebraria a purga seletiva de itens decididos
    (EDG-10). Uma tabela própria também dá ao `CorrectionRepository` (T2) uma porta
    única e escopada por empresa, sem expor registros de auditoria à aplicação.

- **Nulabilidade dirigida pelo ciclo de vida: só é obrigatório o que existe na
  geração; tudo que nasce de uma decisão começa `NULL`.**
  - **Justificativa:** `valor_no_pedido`, `justificativa` e `fonte` são o *snapshot*
    determinístico do momento da geração (SUG-05) e por isso são `NOT NULL`;
    `valor_sugerido` só é preenchido quando há base nos dados do tenant (`None` =
    "sem sugestão", SUG-03), e `decidido_por`/`papel_aprovador`/`decidido_em`/
    `aplicado_em`/`motivo_rejeicao`/`motivo_falha` só existem após a decisão/aplicação.
    Declarar cada um como `Mapped[... | None]` com `nullable=True` deixa explícito no
    próprio ORM que o "não aconteceu ainda" é um estado válido — e impede que um item
    `pendente` seja gravado fingindo ter aprovação. As duas FKs seguem a mesma régua:
    `empresa_id` é sempre obrigatório (isolamento entre empresas), enquanto
    `decidido_por` é opcional porque a fila começa sem decisão, exatamente como
    `AuditLog.user_id`.

- **`status` como `String(20)` com default de ORM `"pendente"`, não um enum nativo do
  Postgres, `Literal` ou `Dict` de domínio.**
  - **Justificativa:** o projeto inteiro já modela estados como texto
    (`ImportJob.status`, `TransportRecord.status`); um enum nativo exigiria `CREATE
    TYPE`/`DROP TYPE` no Alembic e atritaria a portabilidade SQLite↔Postgres que a T1
    exige, e um `Dict`/`Literal` no banco não é mais seguro — a validação real da
    máquina de estados vive na camada de serviço (`CorrectionService`, T5/T6), que
    recusa transições fora de `pendente`. Manter o default no ORM (`default="pendente"`)
    preserva o padrão das demais tabelas: a migration cria a coluna `NOT NULL` sem
    `server_default`, e a linha sempre entra já com estado válido.

- **Dois índices compostos casados com as consultas reais, e nenhum índice "por
  precaução".**
  - **Justificativa:** `(empresa_id, status)` é o prefixo de toda listagem da fila e da
    purga por empresa (`list_by_status`, `purgar_expiradas`), enquanto
    `(empresa_id, tipo, alvo_chave, campo)` é a busca de dedup/idempotência
    (`existe_para`, `abertos_para`) que decide se um item novo é criado ou não. As duas
    colunas de maior seletividade ficam à esquerda, então o mesmo índice serve tanto à
    igualdade por empresa quanto às consultas compostas. Não foi criado índice só para
    `created_at`: a retenção sempre filtra por empresa e status terminal antes de
    comparar a data, e um índice a mais só encareceria a escrita.

- **Migration gerada no padrão da *revision* inicial, com `sa.Uuid()` e
  `DateTime(timezone=True)`, e *downgrade* que remove os índices antes da tabela.**
  - **Justificativa:** reusar os mesmos tipos da `5f1c4d61cc86` garante que o esquema
    compila equivalente em SQLite e Postgres (UUID nativo no Postgres; `CHAR(32)` no
    SQLite) e que `created_at`/`decidido_em`/`aplicado_em` nasçam *timezone-aware*,
    alinhados ao `_agora()` (UTC) do ORM. A ordem do *downgrade* reflete a dependência
    real (índice → tabela), permitindo voltar a `base` de forma limpa — coberto por
    teste. O `down_revision = "5f1c4d61cc86"` encadeia a nova revisão logo após a
    inicial, sem ramificar o histórico.

- **Cobertura de schema em `tests/test_migrations.py`, integrada aos testes existentes
  de upgrade e downgrade.**
  - **Justificativa:** a T1 não tem lógica de negócio a testar, então o contrato é o
    próprio esquema. O upgrade a `head` passa a afirmar `item_correcao`; um novo
    `test_item_correcao_tem_indices` reflete os dois índices por nome; e o downgrade a
    `base` afirma que a tabela some. São testes de integração reais (Alembic contra
    SQLite em arquivo temporário), sem tocar rede.

## 3. Concessões e Escolhas Práticas (Trade-offs)

- **`decidido_por` usa `sa.Uuid()` enquanto `user.id` é `GUID` (FastAPI Users): no
  SQLite os dois serializam diferente (`CHAR(32)` vs `CHAR(36)`), no Postgres ambos são
  `UUID`.** É exatamente o débito já registrado em **AD-027** e já presente em
  `AuditLog.user_id`. Foi aceito aqui porque a T1 é schema-only (nenhum *join* com
  `user` acontece) e porque seguir o padrão consolidado do `AuditLog` é mais seguro do
  que introduzir uma correção de tipos isolada numa task de modelo. A consequência
  prática fica registrada em Limitações: quando a trilha (F2 P2) precisar exibir o
  aprovador, o caminho é o mesmo contorno `User.id.in_(ids)` do AD-027, ou uma
  migration futura que alinhe os tipos de uma vez.

- **Sem `CHECK`/enum no banco para `status` nem *uniqueness* que impeça dois itens
  abertos para a mesma chave.** A integridade dessas regras fica na camada de serviço
  (dedup por `gerar_fila`, transição só a partir de `pendente`), o que mantém a
  migration simples e portátil. O design já trata a corrida real como *hardening*
  opcional com `UPDATE ... WHERE status='pendente'` + *rowcount* (EDG-04), então travar
  isso no banco agora seria otimização prematura.

- **`aprovado` existe como estado válido, mas no F2 a aplicação é síncrona.** O estado
  intermediário é observável por muito pouco tempo; mantê-lo é o que permite um *apply*
  desacoplado no futuro sem nova migration. É custo de modelagem hoje por opcionalidade
  amanhã — barato em uma coluna de texto.

- **Sem índice para `created_at` isolado.** Aceitável porque a purga é sempre escopada
  por empresa/status; se a retenção global um dia varrer a tabela sem filtro de empresa,
  o índice `(empresa_id, status)` deixa de bastar e isso vira uma migration de
  acompanhamento.

### Limitações conhecidas

- **Resolução do aprovador no SQLite esbarra em AD-027:** `decidido_por` (`CHAR(32)`) e
  `user.id` (`CHAR(36)`) não casam em *join* direto. A trilha que precisar do e-mail do
  aprovador deve usar `User.id.in_(ids)` (ou aguardar a migration de alinhamento de
  tipos). No Postgres o *join* funciona.
- **Validade do `status` não é garantida pelo banco:** um `INSERT` manual fora do ORM
  pode gravar qualquer string de até 20 caracteres; a máquina de estados é responsabilidade
  de `CorrectionService`.
- **Sem constraint de dedup:** nada no banco impede dois itens `pendente` para a mesma
  `(tipo, alvo_chave, campo)`; a idempotência depende de `gerar_fila` (EDG-01/EDG-04).
- **Sem *relationship* ORM para `Empresa`/`User`:** o acesso a esses agregados é sempre
  explícito via repositório, coerente com `StockItem`, `AuditLog` e demais tabelas; a
  modelagem por *join* fica na camada de consulta, não no grafo de objetos.

## 4. O que vem a seguir (Roadmap Imediato)

- **T2 (`CorrectionRepository`):** dá ao modelo a única porta de SQL escopada por
  empresa, servindo a dedup (`existe_para`/`abertos_para`), a trilha P2 e a purga — sem
  a qual a fila não materializa nem respeita retenção.
- **T5/T6 (Serviço e eventos):** a máquina de estados que o schema deixa em aberto
  (validade de `status`, transição só a partir de `pendente`) nasce no serviço, apoiada
  nas colunas de decisão/aplicação modeladas aqui.

## 5. Validação de Qualidade e Segurança

- **Garantias de negócio e isolamento:** `empresa_id` é sempre obrigatório e a nova
  tabela não guarda o texto livre fora de `justificativa`/`motivo_*` (campos do próprio
  item, não da auditoria); o schema é portátil entre SQLite e Postgres e o *downgrade*
  volta a `base` limpo, coberto por teste.
- **Cobertura e testes automatizados:** `tests/test_migrations.py` afirma o upgrade a
  `head` (tabela `item_correcao`), os dois índices por nome
  (`test_item_correcao_tem_indices`) e a remoção no downgrade — integração real do
  Alembic contra SQLite em arquivo temporário, sem rede. Suíte completa no gate do PR:
  **287 passed, 98,39%** (gate de 80% ok).
- **Padrões de qualidade:** `uv run black` e `uv run ruff check` verdes;
  `from __future__ import annotations` presente; docstrings em português; sem
  comentários fora de docstring; migration no padrão da *revision* inicial.
