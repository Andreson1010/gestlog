# ADR: pr74-review-followups

## 1. Context & Goal

O code review do PR #74 (matriz de dialetos no CI) deixou três follow-ups: um
MEDIUM (o SQLite do gate local não aplicava chaves estrangeiras, então a suíte
podia gravar `Membership`/`StockItem` órfãos e passar onde o Postgres recusaria),
um LOW sobre `from apoio import ...` depender do `sys.path` implícito do pytest e
um LOW de documentação (o job `postgres` também exige `CONNECT` no banco de
manutenção, não só `CREATEDB`).

O objetivo é fechar os três sem alterar comportamento de produção. O desafio
central é o primeiro: `PRAGMA foreign_keys` não é atributo do schema, é da
**conexão**, e o SQLite nasce com ele desligado. Um teste de FK órfã só prova algo
se o pragma estiver ativo exatamente na conexão que a sessão usa — o que exige
aplicá-lo antes do primeiro DML, em toda conexão que o engine abrir, e sem
transformar isso em regra global do código de produção.

## 2. Architectural Decisions

- **Decision 1: ligar o pragma no evento `connect` do engine, dentro de `db_session`.**
  - **Justification:** `PRAGMA foreign_keys` é por conexão e é ignorado se emitido
    dentro de uma transação ativa; o evento `connect` dispara quando a conexão
    DBAPI nasce — antes de `init_db`/`create_all` e de qualquer DML — e cobre
    tanto o `StaticPool` do `:memory:` quanto um pool futuro com mais de uma
    conexão (`tests/conftest.py:104-116`, chamado em `tests/conftest.py:130`).
    Registrar o listener no engine do fixture, e não em `build_engine`, mantém a
    produção intocada: `build_engine` é código de `libs` compartilhado por
    app/CLI/web, e impor FK nele mudaria semântica de produção por causa de um
    requisito de teste. Alternativa descartada: repetir o pragma em cada
    `create_engine` dos testes — fácil de esquecer no próximo fixture.

- **Decision 2: o teste de regressão usa o próprio `db_session` e insere
  `Membership` com `user_id`/`empresa_id` aleatórios (`tests/test_db.py:108`).**
  - **Justification:** o conserto vive no fixture; só exercitando o fixture o
    teste falha quando o pragma desaparece (verificado: sem o pragma o insert
    órfão é aceito e o teste quebraria; com ele, `IntegrityError`). `Membership`
    foi escolhido porque as duas colunas de FK são `NOT NULL` e as demais
    (`papel`, `created_at`) têm default, e o par aleatório de `uuid4` não colide
    com `uq_membership` — logo o `IntegrityError` só pode vir da FK. A asserção
    fica ancorada no efeito do critério, não em "algum erro" (L-029).

- **Decision 3: `pythonpath = ["src", "tests"]` no `pyproject.toml:82`, em vez de
  mexer em `sys.path` no `conftest`.**
  - **Justification:** `from apoio import ...` funcionava por acidente — o pytest
    insere o diretório-base no `sys.path` no modo `prepend` (o atual), o que
    deixaria de valer ao adotar `--import-mode=importlib`. A
    opção `pythonpath` é declarativa, vale para toda a suíte e não tem efeito fora
    do pytest; produção não é afetada.

- **Decision 4: documentar `CONNECT` no banco `postgres` e o pragma no `TESTING.md`.**
  - **Justification:** `_executar_admin` conecta no banco de manutenção para
    `CREATE DATABASE`/`DROP DATABASE`; sem `CONNECT` ali, o erro do Postgres não
    aponta para privilégio e a matriz parece "quebrada". A nota do pragma explica
    por que o gate local agora pega FK órfã sem Postgres, evitando que alguém
    remova o listener achando que é redundante com o CI.

## 3. Trade-offs & Compromises

- **Escopo do pragma limitado ao `db_session`.** Fechar o MEDIUM em todo engine de
  teste exigiria tocar os fixtures de `tests/web/` e `tests/acceptance/` (fora do
  escopo aprovado) ou ligar FK em `build_engine` (mudança de produção). Aceitável
  porque a camada de modelos/repositórios — onde o achado apareceu — é toda
  `db_session`.
- **Custo por teste: uma instrução por conexão.** Com `StaticPool` no `:memory:` é
  uma conexão por teste (microssegundos) e o listener só existe no engine do
  fixture; impacto não mensurável.
- **Testes podem falhar mais cedo.** Um insert órfão que antes passava agora
  levanta `IntegrityError` — comportamento desejado, mas é mudança de contrato
  *dos testes*; por isso o gate completo foi reexecutado. Neste worktree: `black`
  e `ruff` limpos, `tests/test_db.py` 7 passed; a suíte completa deu 571 passed e
  2 falhas em `tests/copilot/test_service.py`, **pré-existentes e alheias a este
  diff** — reproduzidas com `tests/conftest.py` revertido (`git stash`): 2 a 4
  falhas em 28 testes do módulo. A causa é ordenação por `created_at` empatado no
  mesmo microssegundo (20/20 rodadas com timestamp repetido no ambiente Windows),
  não a FK.
- **Teste redundante no Postgres.** Sob `GESTLOG_TEST_DATABASE_URL` ele passa pela
  razão nativa do Postgres, não pelo pragma; quem guarda o pragma é o job SQLite.
  Custo desprezível, benefício de manter um único teste dialetal.
- **`tests` no `sys.path`.** Amplia a superfície de import (um `apoio.py` ou um
  diretório de teste pode sombrear um nome de terceiro), mas só dentro do pytest;
  a alternativa (`tests/` como pacote com `__init__.py`) seria invasiva para o
  ganho.

## 4. Known Limitations

- O pragma é verificado pelo efeito (FK órfã rejeitada), não por asserção direta
  de `PRAGMA foreign_keys`; essa consulta é dialetal e falharia no Postgres.
- Fixtures com engine próprio (`tests/web/`, `tests/acceptance/`,
  `tests/test_migrations.py` e o `engine` de `tests/test_db.py`, que só inspeciona
  schema) continuam sem FK no SQLite: o MEDIUM está fechado
  para a camada de modelos/repositórios, não para todos os engines de teste.
- O teste não distingue qual das duas FKs disparou o `IntegrityError`; cobrir cada
  coluna separadamente exigiria criar empresas/usuários válidos e não muda o
  diagnóstico do pragma.
- Nenhum modelo declara `ondelete`; quando houver cascata real, o pragma passará a
  valer também para ela e o teste atual não cobre esse caminho.
