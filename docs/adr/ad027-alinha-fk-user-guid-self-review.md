# ADR: ad027-alinha-fk-user-guid

## 1. Contexto & Objetivo

O gestlog autentica com o FastAPI Users, cuja tabela base
(`SQLAlchemyBaseUserTableUUID`) declara `User.id` como `GUID` — um tipo que, no
SQLite, grava `str(uuid)` (**36 caracteres, com hífens**) e, no Postgres, usa o
`UUID` nativo. As colunas que apontavam para esse usuário foram criadas, em
contrapartida, com o `Uuid` do SQLAlchemy, que no SQLite grava `value.hex`
(**32 caracteres, sem hífens**) e no Postgres também usa `UUID` nativo. A
divergência era invisível em produção (Postgres), mas quebrava no banco de
desenvolvimento e dos testes (SQLite): um `JOIN` direto
`Membership.user_id = User.id` comparava uma string de 32 com outra de 36 e
voltava vazio.

O sintoma prático estava em `auth/accounts.py::listar_usuarios`, que contornava
o problema buscando os vínculos e depois os usuários com `User.id.in_(ids)` — o
`IN` funciona porque o id é desserializado para um objeto `UUID` e re-serializado
no formato da coluna de destino. O contorno, porém, mantinha o débito AD-027 e
trazia dois custos latentes: impedia um relacionamento ORM direto
`Membership.user` e descartava em silêncio vínculos cujo usuário não casasse,
mascarando dados órfãos. A meta desta entrega é remover a assimetria de tipos que
originou o contorno, tornando o `JOIN` correto por construção nos dois dialetos.

## 2. Decisões de Arquitetura

**1. Alinhar as cinco FKs a `GUID` — e não `User.id` a `Uuid`**

O movimento natural seria "igualar os dois lados"; a pergunta é qual lado muda.
`User.id` pertence ao contrato do FastAPI Users: é definido pela tabela base do
framework e consumido pelo gerenciador de autenticação. Reescrevê-lo para `Uuid`
significaria redefinir um tipo que não é nosso, brigar com a biblioteca e
arriscar a persistência e a leitura de sessões — um risco de autenticação em
troca de nenhum ganho. O `GUID` do FastAPI Users já é exatamente o
`TypeDecorator` que queremos nas bordas: resolve para `UUID` nativo no Postgres,
para `CHAR(36)` com `str(value)` no SQLite, e devolve `UUID` em ambos. Alinhar o
lado **dependente** (as FKs) é, portanto, a mudança menor e a que preserva o
contrato do framework. As cinco colunas passaram a `GUID`
(`db/models.py`): `membership.user_id`, `conversation.user_id`,
`feedback.user_id`, `audit_log.user_id` e `item_correcao.decidido_por`.

**2. Normalizar as cinco FKs em conjunto, numa migração de dados dialeto-aware**

Alinhar só `Membership` resolveria o sintoma visível, mas deixaria quatro
`JOIN`s latentes quebrados (`conversation`, `feedback`, `audit_log`,
`item_correcao`). A decisão foi tratar as cinco de uma vez, iterando um único
conjunto `_COLUNAS`, para que o alinhamento seja completo e não volte como débito
disfarçado. Como no Postgres as duas representações já são `UUID` nativo e o dado
está consistente, a migração (`alembic/versions/b7d2e9a4f108_alinhar_fk_user_guid.py`)
é **de dados e sensível ao dialeto**: no SQLite converte cada valor de 32 para 36
caracteres (`substr`/`replace`), nos demais dialetos é no-op. O `WHERE length = 32`
torna o `upgrade` idempotente e o `WHERE length = 36` torna o `downgrade`
reversível, ambos sem tocar em linhas já no formato correto.

**3. `batch_alter_table` foi deliberadamente evitado**

A alternativa "correta" no papel seria um `batch_alter_table` para trocar o tipo
declarado das colunas. No SQLite essa operação **recria as tabelas** (copia para
uma tabela nova, troca de nome), o que em cinco tabelas de catálogo
(`membership`, `conversation`, `feedback`, `audit_log`, `item_correcao`) põe em
risco constraints e índices — notoriamente o `uq_membership` — e reescreve a
árvore inteira. E o ganho seria nulo: no SQLite o tipo declarado `CHAR` tem
afinidade **TEXT** e não impõe comprimento, então armazenar 36 caracteres numa
coluna declarada `CHAR(32)` é perfeitamente válido. O que importa de fato é o
**formato do valor gravado**, porque é ele que o `GUID` usa no bind e na leitura.
Por isso a migração corrige dados, não DDL. A decisão é pragmática e estável:
evita um rebuild arriscado e entrega o comportamento correto em ambos os bancos.

**4. `listar_usuarios` resolve o usuário por `JOIN` direto**

Com os dois lados usando `GUID`, o workaround `User.id.in_(ids)` deixa de ser
necessário e vira ruído: `listar_usuarios` passa a
`select(Membership, User).join(User, Membership.user_id == User.id)`, mantendo o
`WHERE` por empresa, a ordenação (`created_at`, `id`) e o contrato de retorno
`list[tuple[Membership, User]]`. Além de mais barato (uma consulta em vez de
duas), o `JOIN` elimina a ambiguidade de vínculos órfãos e habilita, no futuro,
um relacionamento ORM direto sem reescrita.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **O DDL das colunas no SQLite continua `CHAR(32)`:** só os dados foram
  normalizados. É seguro pela afinidade TEXT descrita acima, mas significa que o
  schema físico do SQLite não reflete o modelo `GUID`. Um `alembic autogenerate`
  futuro pode acusar esse *drift* e sugerir um rebuild; se isso incomodar, um
  batch controlado (e coberto por teste) resolve depois. Enquanto o SQLite for
  banco de dev/teste, o custo é aceitável frente ao risco de perder índices.
* **O caminho Postgres da migração não é exercido no CI:** os testes de migração
  rodam sobre SQLite, então o ramo "não é SQLite → no-op" não é executado por
  teste. A justificativa é que o Postgres já era consistente (ambos `UUID`
  nativo) e que o próprio `GUID` resolve para `UUID` nativo no dialeto — o
  caminho é no-op por construção. Ainda assim é uma lacuna real: adicionar um
  job com Postgres no CI (matriz de dialetos) fecharia o buraco.
* **O teste semeia o legado com SQL cru, não pelo ORM:** é proposital. O cenário
  que a migração corrige é o dado **pré-migração**, gravado no formato `Uuid`
  (32 hex); reproduzi-lo pelo ORM atual (já `GUID`) testaria outra coisa. A
  contraparte fica coberta pelos testes de auth/UI, que criam usuários pelo ORM
  e provam que o `JOIN` real casa. `auth/accounts.py` também segue com SQL na
  camada `auth/` — exceção já documentada na AD-013, não uma novidade desta
  entrega.
* **Sem paginação e sem modelagem da listagem:** a mudança não altera volume nem
  resposta; paginação continua fora de escopo (mesma decisão da T31).

## 4. O que vem a seguir (Roadmap Imediato)

* **Postgres no CI (matriz de dialetos):** rodar `tests/test_migrations.py` e os
  repositórios contra um Postgres efêmero, cobrindo o ramo no-op da migração e o
  comportamento das colunas `UUID` nativas.
* **Relacionamento ORM `Membership.user`:** com os tipos alinhados, o `relationship`
  direto passa a ser viável; adotá-lo simplifica `listar_usuarios` e outros
  consumidores, com `joinedload`/`selectinload` se a listagem crescer.
* **Alinhar o DDL do SQLite (se necessário):** substituir o `CHAR(32)` remanescente
  por `CHAR(36)` via batch controlado, com teste de preservação de
  `uq_membership` e índices, caso o *drift* de autogenerate passe a atrapalhar.
* **Paginação da gestão de usuários:** endpoint e tela são estáveis; paginar só se
  o volume por tenant justificar.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio e privacidade:** o `JOIN` preserva o isolamento entre
  empresas — o `WHERE` continua amarrado a `empresa_id` (o da sessão), de modo
  que o relacionamento usuário↔vínculo nunca atravessa tenants. Não há chamada a
  LLM nem envio de dado pessoal a provedor externo nesta entrega; e-mails só são
  materializados na renderização, como antes. Nenhum segredo é lido ou logado.
* **Cobertura e testes automatizados:** `test_migracao_normaliza_fk_user_para_guid`
  (`tests/test_migrations.py`) sobe até a revisão anterior, semeia uma linha
  legada em **cada uma das cinco** colunas, prova que o `JOIN` retorna 0 antes,
  roda `upgrade head` e prova valor de 36 == `User.id` e `JOIN` == 1 após; em
  seguida faz `downgrade` e prova a reversão (32 de novo, `JOIN` == 0). O
  relacionamento real é exercido por
  `tests/auth/test_admin.py::test_admin_lista_usuarios_da_empresa`,
  `tests/web/test_admin_ui.py::test_pagina_lista_usuarios_da_empresa` e pela
  aceitação da F1. Gate completo: **572 passed, 99,23%**.
* **Padrões de qualidade:** `black --check` + `ruff check` + `pytest` verdes via
  `gestlog-gate` (WSL2/Ubuntu). Tipagem anotada (`Mapped[UUID]`/`Mapped[UUID | None]`),
  `from __future__ import annotations` em todos os módulos, docstrings e nomes em
  português, sem comentários fora de docstring, sem `print`, funções abaixo de 50
  linhas e arquivos abaixo de 800 linhas. Migração com `revision`/`down_revision`
  válidos e head único (`b7d2e9a4f108`).

## Achados corrigidos no self-review

* **Cobertura parcial do conjunto de colunas (média):** o teste da migração
  validava apenas `membership.user_id`, deixando as outras quatro colunas de
  `_COLUNAS` sem asserção — uma reincidência da regra "1 teste por elemento do
  conjunto" (L-029). O teste foi reescrito para semear e verificar as **cinco**
  colunas, ancorado ao dado (valor == 32/36 e efeito no `JOIN`), e ganhou o
  round-trip de `downgrade` com dado legado. Lição registrada em L-037.
* **Sem achados** de correção, segurança (injeção, segredo hardcoded, vazamento
  entre empresas), tipagem ou lint. O SQL da migração interpola apenas nomes de
  tabela/coluna vindos de constantes internas (`_COLUNAS`), nunca de entrada do
  usuário; os valores são sempre bind params.
