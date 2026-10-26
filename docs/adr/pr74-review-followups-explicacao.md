# Explicação detalhada — ADR `pr74-review-followups`

> Documento didático derivado de `docs/adr/pr74-review-followups-self-review.md`.
> Explica a decisão como se o leitor não soubesse nada do assunto.

## 1. Termos técnicos primeiro

Antes da explicação, o vocabulário. Cada termo abaixo aparece no assunto e é definido como se você nunca tivesse visto.

### 1.1 Processo de desenvolvimento

- **ADR (Architecture Decision Record — Registro de Decisão de Arquitetura)**: documento curto que registra *uma decisão técnica*, o porquê, as alternativas descartadas e o que se perdeu. Pense numa "ata de reunião" que o time do futuro lê para entender por que o código está daquele jeito. O assunto aqui é a ADR `docs/adr/pr74-review-followups-self-review.md`.
- **PR (Pull Request)**: pedido para incorporar uma branch ao `main`. É onde o código é revisado antes do merge. Os PRs citados são o **#74** (matriz de dialetos no CI), o **#75** (o ADR `pr74-review-followups-self-review.md` e os consertos) e o **#76** (este documento didático, derivado da ADR do #75).
- **Code review**: revisão por outra pessoa — ou, aqui, por um **subagente** de IA com modelo diferente do autor — que só aponta problemas, nunca corrige.
- **Self-review**: revisão feita pelo próprio autor antes do PR, para polir e registrar decisões (fase 5.5 do fluxo `feature-factory`, descrita em `AGENTS.md:185-195`).
- **Follow-up**: pendência que nasce de uma revisão e fica para depois. Um "a fazer" derivado de um achado.
- **Achado com severidade CRITICAL / HIGH / MEDIUM / LOW**: classificação do impacto de um problema. `MEDIUM` = importa, mas não bloqueia o merge; `LOW` = melhoria/documentação. CRITICAL/HIGH bloqueiam.
- **Gate**: "portão" de qualidade que precisa passar antes de mesclar — testes, cobertura mínima, lint e formatação (`AGENTS.md:16-31`).
- **CI (Continuous Integration — Integração Contínua)**: robô que roda os gates automaticamente a cada push/PR. No projeto, é o GitHub Actions (`.github/workflows/ci.yml`).
- **Job**: uma tarefa dentro do CI. Aqui há dois: `quality` (black + ruff + pytest em SQLite) e `postgres` (pytest contra Postgres), em `.github/workflows/ci.yml:42-77`.

### 1.2 Banco de dados

- **Banco de dados relacional**: organiza dados em **tabelas** com **linhas** (registros) e **colunas** (campos). Exemplo: a tabela `membership` tem colunas `id`, `user_id`, `empresa_id`, `papel`.
- **SQL (Structured Query Language)**: linguagem para consultar/alterar esses bancos (`SELECT`, `INSERT`, `UPDATE`).
- **SQLite**: banco leve, embutido no próprio processo, que pode viver num arquivo ou só na memória (`:memory:`). É usado nos testes locais. Analogia: um "caderno" local, sem servidor.
- **PostgreSQL (Postgres)**: banco cliente-servidor, mais rigoroso, usado em produção (`src/gestlog/config.py:34` aponta para Postgres por padrão). Analogia: um "cartório" central com regras formais.
- **Dialeto**: variação de SQL de cada banco. **Matriz de dialetos** = rodar a mesma suíte em mais de um banco (SQLite e Postgres) para pegar diferenças de comportamento.
- **Chave estrangeira (FK — Foreign Key)**: coluna que "aponta" para o `id` de outra tabela. Exemplo: `Membership.user_id` aponta para `user.id`; `Membership.empresa_id` aponta para `empresa.id` (`src/gestlog/db/models.py:64-65`). Analogia: um crachá que só vale se o funcionário existir no cadastro.
- **Integridade referencial**: a regra de que toda FK precisa apontar para uma linha que existe. Sem ela, o banco aceita "crachá de funcionário fantasma".
- **Linha órfã**: linha cuja FK aponta para um `id` inexistente. Exemplo: uma `Membership` com `user_id` aleatório que não está em `user`.
- **PRAGMA**: comando de configuração do SQLite. `PRAGMA foreign_keys=ON` liga a checagem de FK **naquela conexão**. Analogia: instruir o porteiro a conferir crachás — vale só para o turno dele.
- **Transação**: bloco de operações que vale tudo ou nada. **commit** confirma; **rollback** desfaz.
- **DML (Data Manipulation Language)**: comandos que mexem em dados — `INSERT`, `UPDATE`, `DELETE`. Diferente de DDL (criar tabelas).
- **Banco de manutenção `postgres`**: banco padrão que todo cluster Postgres tem, usado para comandos administrativos como `CREATE DATABASE`. Não confundir com o banco da aplicação (`gestlog`/`gestlog_test`).
- **`CREATEDB` / `CONNECT`**: permissões do Postgres. `CREATEDB` = criar bancos; `CONNECT` = poder se conectar a um banco (inclusive ao `postgres`).

### 1.3 Ferramentas e bibliotecas

- **SQLAlchemy**: biblioteca Python que mapeia classes para tabelas (um **ORM — Object-Relational Mapping**) e conversa com o banco.
  - **Engine**: fábrica de conexões. Fica em `src/gestlog/db/session.py:19-33`.
  - **Pool**: reservatório de conexões reutilizáveis. **`StaticPool`** = uma única conexão compartilhada — é o que o SQLite em memória usa (`src/gestlog/db/session.py:27-32`), porque cada conexão nova ao `:memory:` criaria um banco vazio diferente.
  - **Sessão (`Session`)**: unidade de trabalho do ORM; é o objeto que os testes usam para `add`/`commit`.
  - **DBAPI**: interface padrão do Python para bancos (ex.: módulo `sqlite3`, driver `psycopg`).
  - **Cursor**: objeto que executa comandos SQL na conexão.
  - **Evento `connect`**: gatilho disparado pelo SQLAlchemy no instante em que uma conexão DBAPI nasce. **Listener** é a função registrada para reagir a esse gatilho.
- **pytest**: framework de testes do projeto.
  - **Fixture**: função que prepara um recurso para os testes (ex.: abrir uma sessão de banco).
  - **`conftest.py`**: arquivo onde ficam fixtures compartilhadas (`tests/conftest.py`).
- **`sys.path`**: lista de pastas onde o Python procura um módulo quando você faz `import`. Se `tests/` não está lá, `from apoio import ...` não acha o arquivo.
- **`pythonpath` (opção do pytest)**: configuração declarativa que adiciona pastas ao `sys.path` enquanto os testes rodam.
- **`import-mode=prepend` / `importlib`**: modos como o pytest monta o `sys.path`. No `prepend` (atual), ele insere pastas "por baixo dos panos"; no `importlib`, não insere — imports implícitos quebram.
- **`IntegrityError`**: exceção do SQLAlchemy quando o banco recusa uma operação por violar integridade (FK, unicidade etc.).
- **UUID / `uuid4`**: identificador único de 128 bits; `uuid4()` gera um valor aleatório, praticamente impossível de repetir.
- **`NOT NULL`**: coluna obrigatória.
- **Default**: valor automático quando você não informa (ex.: `papel="operador"`).
- **Unique constraint (`uq_membership`)**: regra de que a combinação `(user_id, empresa_id)` não pode repetir (`src/gestlog/db/models.py:61`).
- **WSL2 (Windows Subsystem for Linux)**: Linux rodando dentro do Windows; é usado neste projeto para rodar o gate porque o Smart App Control do Windows bloqueia partes do SQLite/driver (lição L-035 em `.opencode/LESSONS.md`).
- **LLM (Large Language Model — Modelo de Linguagem de Grande Porte)**: modelo que gera texto; o projeto usa via endpoint compatível com OpenAI e, nos testes, um modelo **fake** (sem rede), como descrito em `AGENTS.md:114-116`.

---

## 2. Decomposição passo a passo

### 2.0 O contexto: o que aconteceu antes desta ADR

O PR #74 colocou a suíte para rodar **também contra Postgres** no CI — a "matriz de dialetos" (`.github/workflows/ci.yml:42-77`, documentada em `docs/specs/codebase/TESTING.md:16-21`). A revisão independente desse PR aprovou, mas deixou três pendências:

1. **MEDIUM** — o SQLite usado nos testes locais **não aplicava FKs**; a suíte podia gravar linhas órfãs e passar, enquanto o Postgres recusaria.
2. **LOW** — `from apoio import ...` funcionava "por acidente", dependendo de como o pytest mexe no `sys.path`.
3. **LOW** — a documentação dizia que criar bancos no Postgres exige `CREATEDB`, mas omitia que também é preciso `CONNECT` no banco `postgres`.

O PR #75 (e este documento didático, entregue no PR #76) existem para fechar exatamente esses três pontos.

### 2.1 Parte 1 — o problema das FKs no SQLite (o achado MEDIUM)

**O que faz e por quê.** O SQLite nasce com a checagem de FK **desligada**. Isso significa que, nos testes locais, inserir uma `Membership` com `user_id` aleatório **funciona** — mesmo que esse usuário não exista. No Postgres, o mesmo `INSERT` falha. Resultado: um teste podia passar em SQLite e quebrar só no CI/Postgres, tarde demais.

Onde isso aparece no código real:

- As relações estão em `src/gestlog/db/models.py:57-69` — `Membership.user_id` → `user.id` e `Membership.empresa_id` → `empresa.id` (`:64-65`), com `uq_membership` em `:61`.
- O problema prático já era conhecido: `tests/apoio.py:1-6` explica que o SQLite "não aplica chaves estrangeiras por padrão" e que os testes precisam semear pais reais (`criar_usuario` em `:18-33`, `criar_empresa` em `:36-42`).
- Os testes recebem sessão pelo fixture `db_session` em `tests/conftest.py:119-147`.

**A correção, passo a passo.** Em `tests/conftest.py:104-116` foi criado o helper `_ligar_fk_sqlite(engine)`:

1. `event.listens_for(engine, "connect")` (`:111`) registra um listener no evento em que uma conexão nasce.
2. Quando a conexão nasce, `_pragma_foreign_keys` (`:112-116`) abre um **cursor** próprio e executa `PRAGMA foreign_keys=ON` (`:114`), depois fecha o cursor.
3. O helper é chamado em `tests/conftest.py:130`, **antes** de `init_db(engine)` (`:131`), que é quem cria as tabelas (`src/gestlog/db/session.py:41-45`). Como `create_all` abre a primeira conexão, o pragma já está ativo antes de qualquer DML.
4. O ramo Postgres do fixture (`:136-147`) não recebe o pragma — e não precisa: o Postgres aplica FKs sempre.

Por que esse formato específico:

- **É por conexão, não por schema.** `PRAGMA foreign_keys` não fica "gravado na tabela"; vale para a conexão. Se você abrir outra conexão, ela nasce com FK desligada de novo. Daí o listener.
- **Precisa ser fora de transação.** No SQLite, o pragma é ignorado se emitido dentro de uma transação ativa. No evento `connect` não há transação aberta.
- **Funciona com o `StaticPool`.** Como o SQLite em memória usa uma única conexão (`src/gestlog/db/session.py:27-32`), configurá-la na criação cobre todos os usos daquele teste.

**Por que não colocar isso em `build_engine`?** `build_engine` (`src/gestlog/db/session.py:19-33`) pertence a `libs` — a fundação compartilhada por `apps`, `agents` e `libs`, conforme as fronteiras em `AGENTS.md:60-76`. Alterar a semântica dele por causa de um requisito de teste mexeria no comportamento de produção. O default de produção é Postgres (`src/gestlog/config.py:34`), mas `build_engine` também atende qualquer configuração com SQLite; impor FK ali seria uma decisão de produto disfarçada de conserto de teste. Por isso o listener vive **só no engine do fixture**.

### 2.2 Parte 2 — o teste que prova o conserto

**O que faz e por quê.** Um conserto sem teste de regressão é uma promessa. O teste novo em `tests/test_db.py:108-112` faz o seguinte:

1. Usa o próprio fixture `db_session` (não cria um engine paralelo).
2. Insere `Membership(user_id=uuid4(), empresa_id=uuid4())` (`:109`) — dois pais inexistentes.
3. Espera `IntegrityError` (`:110-111`) e faz `rollback()` (`:112`).

**Por que `Membership` e não outra tabela?** Porque o teste precisa falhar **só pela FK**, sem ambiguidade:

- `user_id` e `empresa_id` são `NOT NULL` (`src/gestlog/db/models.py:64-65`), então o insert não falha por coluna obrigatória ausente.
- `papel` e `created_at` têm default (`:66-69`), então não falham por isso.
- Os dois UUIDs são aleatórios (`uuid4`) e não colidem com `uq_membership` (`:61`).
- Logo, o único motivo possível para o banco rejeitar é a **FK**.

**Sensibilidade (por que o teste "morde").** Se alguém remover o listener/pragma, o SQLite volta a aceitar o insert órfão; o `pytest.raises(IntegrityError)` não recebe exceção e o teste **falha**. Isso é o que a ADR chama de "ancorar no efeito do critério" (`docs/adr/pr74-review-followups-self-review.md:33-41`), alinhado à lição L-029 (testes devem ancorar no dado/estado real, não em aparência).

**Redundância no Postgres.** Sob `GESTLOG_TEST_DATABASE_URL`, o mesmo teste roda contra Postgres e passa pela razão nativa (FK sempre ligada), não pelo pragma. A ADR aceita essa redundância (linhas 77-79): custa quase nada e mantém **um único teste dialetal**.

### 2.3 Parte 3 — o import de `tests/apoio.py` (o achado LOW do `sys.path`)

**O que faz e por quê.** Seis arquivos de teste importam helpers de `tests/apoio.py`:

- `tests/audit/test_auditoria.py:9`
- `tests/copilot/test_service.py:9`
- `tests/correcoes/test_servico_decisao.py:9`
- `tests/correcoes/test_servico_rejeicao.py:9`
- `tests/test_repositories_relatorios.py:8`
- `tests/test_repositories.py:8`

Esses imports funcionavam porque o pytest, no modo `prepend`, insere diretórios no `sys.path` automaticamente — inclusive o diretório do `conftest.py` raiz. É um comportamento **implícito**: o código não declara que depende dele.

**A correção.** `pyproject.toml:82` passou de `pythonpath = ["src"]` para `pythonpath = ["src", "tests"]`. Com isso, o teste declara explicitamente onde procurar os módulos, em vez de contar com o acidente do modo de import. A opção vale só dentro do pytest — produção não é afetada, porque não está em `src/` nem é importada pela aplicação.

**Alternativa descartada.** Transformar `tests/` num pacote com `__init__.py` (necessário em alguns modos de import). A ADR rejeita (linhas 80-83) porque é invasivo para o ganho: mudaria a forma de todos os testes serem descobertos e importados.

### 2.4 Parte 4 — documentar `CONNECT` (o achado LOW de documentação)

**O que faz e por quê.** Os testes de migração criam um banco Postgres descartável por teste:

- `tests/test_migrations.py:36` roda `CREATE DATABASE ...` e `:41` roda `DROP DATABASE ... WITH (FORCE)`.
- Esses comandos passam por `_executar_admin` (`tests/test_migrations.py:56-60`), que se conecta ao banco de manutenção **`postgres`** (`:59`, `isolation_level="AUTOCOMMIT"`).

Para isso funcionar, o usuário precisa de duas permissões: `CREATEDB` **e** `CONNECT` no banco `postgres`. A documentação antiga citava só `CREATEDB`. Sem `CONNECT`, o erro que aparece é de conexão — e parece "matriz quebrada", não falta de privilégio.

A correção está em `docs/specs/codebase/TESTING.md:16-21`, que agora cita as duas permissões e também explica o pragma do SQLite. O job que reproduz esse cenário está em `.github/workflows/ci.yml:42-60` (service `postgres:16`) e roda os testes em `:77`.

### 2.5 Parte 5 — como a decisão foi validada e registrada

O processo do repositório (descrito em `AGENTS.md:164-195`) exige dois momentos de revisão:

1. **Self-review** pelo subagente `developer-self-reviewer`, que poliu e gerou esta ADR.
2. **Code review independente** pelo subagente `code-reviewer-agent`, em modelo de outro laboratório (DeepSeek em vez de GLM), que só reporta.

Validação executada:

- Gate SQLite via WSL2: **573 passed, 1 skipped, 99,23%** de cobertura.
- Matriz Postgres local: **573 passed, 1 skipped**.
- CI: jobs `quality` e `postgres` verdes.
- Code review: **APPROVE**, sem CRITICAL/HIGH/MEDIUM; dois LOW documentais foram corrigidos na própria ADR.
- Merge: squash `7d7999f` no `main`, branch apagada.

O self-review também registrou um problema **pré-existente e alheio** a este diff: `tests/copilot/test_service.py` falha de forma intermitente no Windows porque dois registros podem ter o mesmo `created_at` no mesmo microssegundo e a ordenação desempata por `id` aleatório. A ADR documenta (linhas 68-76) e o problema **não** foi corrigido aqui — é débito separado.

### 2.6 Onde isso se encaixa na arquitetura do projeto

- O projeto é um **pacote único** (`src/gestlog/`) com três fronteiras conceituais: `apps` (entrada/deploy), `agents` (grafo e domínio) e `libs` (fundação: config, LLM, banco, repositórios) — `AGENTS.md:60-76`. A direção de dependência é `apps → agents → libs`, nunca invertida.
- Tudo o que este PR mudou está **fora** de `src/`: `tests/`, `pyproject.toml` e `docs/`. Ou seja, nenhuma fronteira foi atravessada e nenhum comportamento de produção mudou.
- Os testes espelham `src/` (`AGENTS.md:110-119`) e não tocam rede/LLM; o `db_session` é o ponto único de acesso ao banco nos testes de modelo/repositório.

---

## 3. Nuances e implicações

### 3.1 Decisões de design

1. **Pragma na conexão, não no schema.** SQLite não tem "FK ligada por tabela"; é um estado da conexão. Ignorar isso levaria a um conserto que funciona no primeiro teste e falha no segundo (conexão nova). Por isso o evento `connect`.
2. **Listener no engine do fixture, não na `libs`.** Preserva a semântica de produção e mantém a decisão onde ela pertence: no teste.
3. **Teste no próprio fixture.** Se o teste criasse um engine próprio, ele testaria a si mesmo e não o `db_session`. Usar o fixture é o que garante que remover o pragma quebra o teste.
4. **Teste único para os dois dialetos.** Em vez de um teste "só SQLite", o mesmo teste roda em Postgres. Custo: redundância no Postgres. Benefício: menos código e garantia de que o comportamento é o mesmo.
5. **Configuração declarativa de import.** `pythonpath` no `pyproject.toml` é visível, versionado e vale para toda a suíte; o `sys.path` implícito do pytest não é.

### 3.2 Trade-offs (o que se ganha e o que se abre mão)

| Decisão | Ganho | Custo / concessão |
|---|---|---|
| Pragma só no `db_session` | Gate local pega FK órfã na camada de modelos/repos | Fixtures com engine próprio (`tests/web/`, `tests/acceptance/`, `tests/test_migrations.py`, o `engine` de `tests/test_db.py`) continuam sem FK no SQLite |
| Listener no engine do fixture | Produção intocada; testável e isolado | Um listener por engine/teste (custo de microssegundos) |
| `pythonpath` com `tests` | Import explícito e estável | `tests/` entra no `sys.path`: um arquivo de teste pode, em tese, sombrear um nome de biblioteca |
| Teste dialetal único | Menos duplicação | No Postgres ele não valida o pragma (valida a FK nativa) |
| Não mexer no `build_engine` | Nenhuma mudança de comportamento em `libs`/produção | Quem usar SQLite fora do fixture continua sem FK automática |

### 3.3 Casos-limite e limites conhecidos

- **Transação ativa:** o pragma precisa ser emitido fora de transação; o evento `connect` garante isso. Se alguém mover a chamada para depois de um `BEGIN`, ela pode ser silenciosamente ignorada.
- **Pool com várias conexões:** o listener cobre todas as conexões que o engine abrir; o `StaticPool` atual usa uma só, mas a solução não depende disso.
- **Cascatas (`ON DELETE`):** nenhum modelo declara `ondelete`. Quando houver cascata real, o pragma passará a valer também para ela, e o teste atual não cobre esse caminho (ADR, linha 96).
- **Duas FKs no mesmo teste:** o `IntegrityError` não diz *qual* FK falhou. A ADR assume isso conscientemente (linhas 93-95): separar exigiria criar pais válidos e não mudaria o diagnóstico do pragma.
- **Import-mode futuro:** o `pythonpath` explícito já prepara o terreno para `--import-mode=importlib`; não é preciso mudar agora.
- **Flake pré-existente:** o teste de `tests/copilot/test_service.py` pode falhar no Windows por empate de timestamp — não é regressão deste PR e foi registrado como débito.

### 3.4 O que NÃO está sendo feito (e por quê)

- **Não se liga FK em `build_engine`/produção.** Seria mudar a semântica da aplicação por causa de um requisito de teste — e o default de produção é Postgres, que já aplica FKs (`src/gestlog/config.py:34`).
- **Não se migram todos os fixtures de teste.** `tests/web/` e `tests/acceptance/` usam engines próprios; o achado apareceu na camada de modelos/repositórios, toda em `db_session`. Migrar o resto é melhoria futura, não requisito deste PR.
- **Não se transforma `tests/` em pacote.** O ganho não justifica a mudança estrutural.
- **Não se testa cascata nem se distingue qual FK falhou.** Custo/benefício não compensa para o objetivo (provar que o pragma está ativo).
- **Não se corrige o flake de `created_at`.** É um problema real, mas de outro escopo; foi documentado como débito.
- **Não se mexe em `docs/specs/project/STATE.md`.** Esta é uma correção pequena e a ADR própria já registra a decisão; o STATE é para decisões de arquitetura maiores.

### 3.5 Se isto fosse uma recomendação: o que preserva, o que muda, o que custa

- **Preserva:** o comportamento de produção (`src/` intocado); o contrato dos testes existentes (a suíte continuou passando); a possibilidade de rodar a matriz em Postgres; a arquitetura `apps → agents → libs`.
- **Muda:** o SQLite de teste passa a **rejeitar FKs órfãs** (testes que antes passavam por acidente podem agora falhar — comportamento desejado); o import de `tests/apoio.py` deixa de depender de um detalhe do pytest; a documentação passa a exigir `CONNECT`.
- **Custa:** um comando `PRAGMA` por conexão de teste (desprezível); `tests/` no `sys.path` durante os testes; um pouco de redundância no Postgres; e a necessidade de lembrar que fixtures novos com engine próprio **não** herdam o pragma.

### 3.6 Risco de regressão e como ele é contido

O risco principal é alguém remover o listener achando que o Postgres já cobre tudo. O teste `tests/test_db.py:108-112` existe exatamente para isso: sem o pragma, ele falha imediatamente no gate SQLite. A nota em `docs/specs/codebase/TESTING.md:20-21` explica o porquê, e a ADR registra a decisão para quem chegar depois. É o padrão "deixe uma armadilha que avisa" em vez de confiar na memória do time.
