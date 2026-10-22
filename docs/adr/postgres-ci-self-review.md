# ADR: postgres-ci

## 1. Contexto & Objetivo

O gestlog roda em produção sobre Postgres, mas até aqui a suíte de testes
executava apenas em SQLite — o banco de desenvolvimento. A assimetria foi
registrada como débito na AD-027 (alinhamento das FKs de `user.id` ao GUID do
FastAPI Users): a migração de dados `b7d2e9a4f108` tem dois ramos, e só o do
SQLite era exercido por teste. O outro — o no-op para bancos com `UUID` nativo —
era "correto por construção" e nada mais: nenhuma execução o tocava, e a promessa
da ADR da AD-027 de que o Postgres era consistente permanecia não verificada.
Pior: o SQLite, por padrão, **não aplica chaves estrangeiras**, então testes
podiam gravar `user_id`/`empresa_id` fictícios e passar em verde, escondendo
violações que o banco de produção rejeita na hora.

O objetivo desta entrega é fechar a lacuna com uma **matriz de dialetos**: o CI
ganha o job `postgres` com um Postgres efêmero rodando a suíte inteira, e os
testes de banco passam a ser dialeto-aware — o mesmo conjunto de testes, dois
bancos, zero alteração no código de produção. Para quem opera o sistema, o ganho
é direto: o comportamento que roda em produção passa a ser exercitado a cada PR,
em vez de depender de um banco de desenvolvimento mais permissivo que o real.

## 2. Decisões de Arquitetura

**1. `db_session` dialeto-aware: transação externa + savepoints no Postgres**

O isolamento entre testes no SQLite em memória é "grátis" — cada teste ganha um
banco novo. No Postgres, recriar o schema por teste seria caro e desnecessário;
a solução foi reproduzir o mesmo isolamento com transações. Com
`GESTLOG_TEST_DATABASE_URL` definida, o fixture `db_session` abre uma conexão,
inicia uma transação externa (`conexao.begin()`) e cria a `Session` com
`join_transaction_mode="create_savepoint"` e `expire_on_commit=False` — a mesma
semântica do `build_session_factory` usado no SQLite. O efeito prático: os
`session.commit()` que os serviços chamam internamente viram *releases* de
savepoint, e os `rollback()` internos (como o de
`CorrectionService._falhar_apos_erro`) desfazem apenas o savepoint corrente, sem
derrubar o que o teste já confirmou. No teardown, `session.close()` e o rollback
da transação externa descartam tudo — nenhum teste enxerga resíduo de outro, e a
suíte roda sequencial sobre um schema criado uma única vez por sessão
(`engine_postgres`, `session-scoped`, com `init_db`). Sem a variável, o fixture
segue idêntico ao anterior (SQLite em memória), então o gate local continua
rápido e sem dependências externas.

**2. `alembic_config` cria e derruba um banco descartável por teste no Postgres**

Testes de migração exigem um banco virgem — não dá para compartilhar o banco da
matriz, que tem o schema de `init_db` e dados de outros testes. Por isso, no
dialeto Postgres, o fixture cria um banco exclusivo por teste
(`gestlog_mig_<hex12>`) via conexão administrativa no banco `postgres` com
`isolation_level="AUTOCOMMIT"` (DDL de `CREATE/DROP DATABASE` não roda dentro de
transação), e o derruba no teardown com `DROP DATABASE ... WITH (FORCE)` — o
`FORCE` garante a limpeza mesmo com conexões residuais de uma falha. A URL do
banco descartável é derivada da URL da matriz com
`make_url(url).set(database=nome).render_as_string(hide_password=False)`: sem o
`hide_password=False`, a senha sairia mascarada (`***`) e a conexão falharia —
detalhe pequeno, mas que quebraria todo o fixture. No SQLite, o fixture continua
usando um arquivo temporário por teste.

**3. O ramo no-op da migração ganhou teste próprio, e o teste SQLite ganhou guard**

O novo `test_migracao_postgres_nao_altera_fk_user` sobe até a revisão anterior
(`c4a81f0d9e2b`), semeia as cinco colunas do conjunto com um `user.id` de
verdade em formato nativo (`str(uuid4())`), e prova que `upgrade head` e
`downgrade` **não alteram nada**: valor inalterado e `JOIN` direto
`t.coluna = "user".id` retornando 1 antes e depois. O teste de dados legados do
SQLite ganhou guard de dialeto (`pytest.skip` quando não é SQLite), porque dado
de 32 caracteres sem hífen só existe nesse banco — é ele o "1 skipped" de cada
execução, um em cada dialeto. Juntos, os dois testes cobrem os dois ramos da
migração através da matriz, ancorados ao dado e ao efeito no `JOIN` (1 asserção
por coluna do conjunto, conforme L-029/L-037), incluindo o round-trip de
`downgrade` com dado.

**4. FKs órfãs: pais reais persistidos via `tests/apoio.py`, com `commit` deliberado**

A primeira execução da matriz expôs a dívida anunciada: **53 testes** semeavam
`user_id`/`empresa_id` fictícios e só passavam porque o SQLite não aplica FK. O
novo `tests/apoio.py` centraliza os dois pais usados como referência —
`criar_usuario` e `criar_empresa` — e os testes passaram a persistir o pai de
verdade antes de referenciá-lo. O `commit` dentro dos helpers não é cosmético: no
modo savepoint, o `rollback()` interno de um serviço desfaria a inserção do pai
ainda pendente, e a decisão seguinte (que grava `item_correcao.decidido_por`,
`audit_log.user_id`, etc.) violaria a FK. Confirmar o pai antes da decisão é o
que permite ao teste exercitar o fluxo real de erro/rollback do serviço com o
banco aplicando as mesmas restrições da produção. Os call sites remanescentes de
`uuid4()` como `user_id` foram auditados um a um: todos estão em caminhos que
levantam exceção **antes** de qualquer escrita (404/409/422), então não geram
linha órfã. O SQL cru dos testes também foi portado: `"user"` entre aspas
(palavra reservada no Postgres) e `TRUE/FALSE` em vez de `1/0`.

**5. Job `postgres` no CI: suíte inteira, com `--no-cov`**

O job usa o service `postgres:16` com healthcheck (`pg_isready`) e expõe
`GESTLOG_TEST_DATABASE_URL` no nível do job; os passos são os mesmos do job
`quality` (checkout, uv, Python 3.12, sync) e o pytest roda **a suíte inteira**
com `--no-cov`. Rodar tudo — e não só os arquivos "de banco" — é o que impede a
matriz de apodrecer: qualquer teste novo que use `db_session` entra nela
automaticamente. O `--no-cov` é porque a cobertura tem um único dono, o job
`quality`; duplicá-la aqui só somaria tempo sem sinal novo. O usuário do service
é o superusuário do container oficial, o que dá a permissão de `CREATEDB`
exigida pelos bancos descartáveis dos testes de migração.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **A matriz cobre `db_session` e as migrações; web/auth/aceitação seguem em
  SQLite:** esses grupos montam o app com engines e fixtures próprios (async e
  arquivo), migrá-los exigiria um recorte à parte. A consequência é honesta: a
  classe de erro "FK órfã" ainda pode se esconder nesses testes (a aceitação da
  F2, por exemplo, semeia `uuid4()` como aprovador), e aparecerá no dia em que
  migrarem. Os testes da camada de modelos (`tests/test_db.py`) ficaram de fora
  na primeira versão e **foram migrados no self-review** (ver achados), fechando
  a contradição com a matriz de cobertura do `TESTING.md`.
* **`DROP DATABASE ... WITH (FORCE)` exige Postgres 13+:** o CI fixa
  `postgres:16` e o `TESTING.md` documenta a dependência. Um banco
  `gestlog_mig_*` deixado por uma execução interrompida não é varrido
  automaticamente — inofensivo no CI efêmero e no container local, que podem ser
  recriados.
* **Sem cobertura no job `postgres`:** `--no-cov` evita computar duas vezes o
  mesmo número; se um dia a suíte em Postgres divergir na cobertura, o job
  `quality` continua sendo a fonte de verdade.
* **Duplicação residual de helpers de empresa:** os `_empresa`/`_empresas`
  locais dos arquivos tocados continuam existindo ao lado de `criar_empresa`.
  Consolidá-los é mecânico, mas espalharia o diff por arquivos fora do escopo
  desta entrega; ficou registrado como limpeza futura.

## 4. O que vem a seguir (Roadmap Imediato)

* **Migrar web/auth/aceitação para a matriz:** maior superfície restante em
  SQLite; pré-requisito é corrigir as FKs órfãs que a migração expuser (ex.:
  aprovador fictício na aceitação da F2). Fecha a classe de erro por completo.
* **Relacionamento ORM `Membership.user`:** follow-up da AD-027 que os tipos
  alinhados habilitam; simplifica `listar_usuarios` e consumidores.
* **Débito herdado `String(4000)`/`Text`:** migração pontual em
  `message.conteudo_redigido`/`recommendation.texto`; a matriz agora protege
  esse tipo de mudança nos dois dialetos.
* **Proteção de branch com o job `postgres` obrigatório:** garantir que a matriz
  seja gate de merge, não apenas um job informativo.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio e privacidade:** nenhum teste toca rede/Ollama; as
  credenciais do service (`gestlog`/`gestlog`) são efêmeras e locais ao runner —
  nenhum segredo real entra no repositório. O isolamento entre empresas passa a
  ser exercitado contra um banco que **aplica** as FKs, de modo que vínculos
  órfãos e violações cross-tenant não podem mais passar despercebidos; cada
  teste é revertido no teardown, sem resíduo entre execuções.
* **Cobertura e testes automatizados:** gate SQLite (WSL2): **572 passed, 1
  skipped, 99,23%**; matriz Postgres local (container 16): **572 passed, 1
  skipped**. O ramo no-op da `b7d2e9a4f108` tem teste dedicado
  (`test_migracao_postgres_nao_altera_fk_user`) e o ramo SQLite mantém o
  round-trip completo com dado legado. **120 funções de teste** usam `db_session`
  e rodam nos dois dialetos (medido; inclui `tests/test_db.py` após o
  self-review), além dos testes de migração. Os 53 testes de FKs órfãs foram
  corrigidos com pais reais via `tests/apoio.py`.
* **Padrões de qualidade:** `black --check` + `ruff check` + `pytest` verdes via
  `gestlog-gate`; YAML do workflow validado por parser; `from __future__ import
  annotations`, docstrings e nomes em português, sem comentários fora de
  docstring, sem `print`; funções ≤ 50 linhas e arquivos ≤ 800 linhas.

## Achados corrigidos no self-review

* **Cobertura da matriz incompleta na camada de modelos (média):**
  `tests/test_db.py` mantinha fixture de sessão própria em SQLite, apesar de a
  matriz de cobertura do `TESTING.md` prometer "DB models ... Postgres no CI".
  Os três testes de dados passaram a usar `db_session` (6 passed nos dois
  dialetos); apenas `test_sqlite_memoria_usa_static_pool` segue específico do
  SQLite, por natureza. Lição registrada em L-038.
* **Afirmação de cobertura imprecisa na AD-031 (baixa):** o STATE dizia "~92
  testes" com `db_session`; a medição real é 117 (120 após a migração do
  `test_db.py`). Número corrigido no `STATE.md`, que também ganhou
  `tests/test_db.py` no Impact.
* **Sem achados** de correção, segurança, tipagem ou lint no restante do diff.
  A revisão confirmou, ponto a ponto: o `commit` dos helpers é necessário e
  seguro (o rollback interno dos serviços não derruba pai confirmado); os
  `uuid4()` remanescentes como `user_id` estão em caminhos que levantam exceção
  antes de escrever; o teste Postgres agrega ao do SQLite (cobre o ramo oposto
  da migração) em vez de duplicá-lo; o teardown do `db_session` em savepoint
  devolve a conexão limpa ao pool.
