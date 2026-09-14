# ADR: t13-upload-ui

## 1. Context & Goal

A T13 entrega a UI de upload e de histórico de importação (requisitos ING-01 e
ING-03). A camada web do gestlog é assíncrona (FastAPI), mas o serviço de
importação construído nas T11/T12 (`ingestion.importar()` e
`ingestion.historico()`) é síncrono e opera sobre `sqlalchemy.orm.Session`.
O desafio técnico central é integrar uma operação bloqueante (parse + upsert +
persistência de um `ImportJob`) numa aplicação async sem travar o event loop,
mantendo a coerência de tenancy e permitindo que a mesma base de dados seja
acessada por sessões async (auth) e sync (importação).

## 2. Architectural Decisions

- **Decision 1:** Handlers de importação declarados como `def` (síncronos) em vez
  de `async def`.
  - **Justification:** O FastAPI executa rotas `def` no threadpool padrão, então o
    parse e a escrita síncrona do arquivo acontecem fora do event loop. Se fossem
    `async def`, o bloqueio em `importar()` congelaria o loop e degradaria todas
    as demais requisições. Isso preserva o modelo mental "camada web async,
    serviço de importação sync" sem reescrever a T12.
- **Decision 2:** Dependência `get_sync_session` fornecendo uma `Session` síncrona
  por requisição, com engine e `sessionmaker` memoizados via `lru_cache`.
  - **Justification:** A T12 assina `importar(session, empresa_id, ...)` com
    `Session`. Em vez de criar um engine a cada chamada (caro: abrir pool,
    conectar), o engine é construído uma única vez e a fábrica de sessões também,
    reaproveitados em todas as requisições. Isso também dá um ponto único de
    injeção para os testes substituírem a sessão síncrona por `dependency_overrides`
    apontando para um arquivo SQLite compartilhado.
- **Decision 3:** Resolução da empresa pela dependência `get_current_empresa`
  (do módulo auth) em vez de receber um parâmetro de corpo ou rota.
  - **Justification:** A empresa é derivada da sessão autenticada (membro da
    tenancy), não de entrada do usuário. Isso satisfaz o isolamento por tenant do
    spec (ING-03) sem expor `empresa_id` manipulável; o histórico e o upload
    operam sempre na empresa da sessão. `pagina_importar` usa o usuário opcional
    e redireciona ao login, mantendo a navegação não autenticada coerente com o
    restante da app.
- **Decision 4:** Erros de importação (`ErroImportacao`) capturados com rollback e
  renderizados como resposta parcial HTMX em `importar_resultado.html`.
  - **Justification:** `analisar()` levanta `ErroImportacao` (tipo desconhecido,
    arquivo vazio, colunas ausentes) antes de qualquer escrita, mas a sessão pode
  conter mudanças pendentes; o rollback garante o invariante "arquivo inválido não
  altera dados" (AC5) e devolve uma mensagem clara no próprio alvo do formulário,
  sem trocar de página. Isso dá feedback em tempo real ao admin.
- **Decision 5:** Templates Jinja2 (HTML) com valores renderizados por
  autoescaping, e CSS no `static/app.css`.
  - **Justification:** O Jinja2 autoescapa expressões `{{ }}` por padrão, o que
    mitiga XSS ao exibir `erro`/`motivo`/`tipo` vindos do usuário. O CSS segue a
    convenção já usada em `app.css` (variáveis `--cor-*`), reutilizando o tema.

## 3. Trade-offs & Compromises

- **Sessão síncrona dedicada em vez de reusar a assíncrona do auth:** o auth é a
  única camada async de banco (AD-013), então a importação precisou de um segundo
  engine (sync) apontando para a mesma base. Isso duplica a configuração de
  conexão, mas evita converter toda a T12 para async (custo alto fora do escopo do
  MVP). A aceitabilidade vem do spec: as T11/T12 são explícitas sobre o serviço
  sync.
- **Sem limite de tamanho de upload em `arquivo.file.read()`:** o conteúdo é lido
  integralmente em memória. É aceitável para arquivos CSV de importação do MVP
  (potencialmente grandes, porém finitos); um limite (ex.: streaming ou
  `max_upload_size`) fica para iteração posterior, pois não compromete o critério
  de aceite atual.
- **Aplicar + commit manual no handler em vez de um `unit of work` do serviço:** a
  T12 não expõe transação própria, então o handler controla `commit`/`rollback`.
  Isso mantém a T12 intacta e o controle transacional explícito no ponto de
  fronteira web. Erros de banco não-`ErroImportacao` (ex.: `IntegrityError`)
  ainda resultam em 500, sem fuga de detalhes internos — aceitável no MVP.

## 4. Known Limitations

- **CSRF:** `POST /importar` não tem proteção CSRF explícita. Isso é coerente com o
  restante da app (auth e onboarding também não têm), mas endpoints de mudança de
  estado protegidos apenas por cookie de sessão deverão ganhar proteção CSRF antes
  de produção.
- **Sem limite de tamanho/valor máximo de upload** (ver Trade-offs).
- **Engine síncrono sempre deriva de `get_settings()`:** o `lru_cache` de
  `_get_sync_engine` usa as configurações globais, ignorando um eventual
  `settings` customizado passado a `create_app`. Em produção a fonte é única
  (`get_settings`), e nos testes a sessão sync é substituída via
  `dependency_overrides`, então não há impacto hoje; seria revisitado se a app
  passar a ser instanciada com configurações diferentes por runtime.
- **Erros de banco inesperados** (não `ErroImportacao`) não produzem mensagem
  amigável; apenas o erro HTTP 500 padrão.
