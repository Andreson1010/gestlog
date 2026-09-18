# ADR: t13-upload-ui

## 1. Contexto & Objetivo

Quem opera o gestlog precisava de uma forma de colocar os próprios dados para
dentro do sistema: antes da T13, o copiloto não tinha o que consultar. A T13
entrega a tela de upload e a de histórico de importação (ING-01 e ING-03), que
transformam arquivos CSV do operador em dados de estoque, fornecedores e
transporte, com um retorno claro sobre o que entrou e o que foi rejeitado. O
desafio central não é a tela em si, e sim a **costura de mundos diferentes**:
a camada web é assíncrona (FastAPI, AD-013), mas o serviço de importação
construído nas T11/T12 (`ingestion.importar()` e `ingestion.historico()`) é
síncrono e opera sobre `sqlalchemy.orm.Session`. Integrar um parse + upsert +
gravação de `ImportJob` — bloqueantes por natureza — numa aplicação async exige
não travar o event loop, manter o isolamento entre empresas e deixar a mesma
base acessível tanto pela sessão assíncrona do auth quanto pela síncrona da
importação.

## 2. Decisões de Arquitetura

**1. Handlers de importação síncronos (`def`), não `async def`**

O FastAPI executa rotas declaradas como `def` no threadpool padrão, então o parse
e a escrita do arquivo acontecem fora do event loop. Se fossem `async def`, o
bloqueio dentro de `importar()` congelaria o loop e degradaria todas as demais
requisições do sistema. Declarar os handlers como `def` preserva o modelo mental
“web assíncrona, serviço de importação síncrono” sem reescrever a T12 — uma
decisão de uma palavra que evita um refactor amplo fora do escopo do MVP.

**2. `get_sync_session` com engine e `sessionmaker` memoizados**

A T12 assina `importar(session, empresa_id, ...)` com uma `Session`; em vez de
criar um engine a cada requisição — caro, porque abre pool e conexão — o engine é
construído uma única vez e a fábrica de sessões também, ficando `get_sync_session`
como o ponto único de injeção. Isso permite que os testes substituam a sessão
síncrona por `dependency_overrides` apontando para um arquivo SQLite
compartilhado, sem tocar rede nem banco real.

**3. A empresa vem da sessão autenticada, nunca do cliente**

As rotas resolvem o tenant por `get_current_empresa` (do módulo auth) em vez de
aceitarem um `empresa_id` de corpo ou rota. O isolamento por tenant exigido pelo
spec (ING-03) não depende de validação de entrada: upload e histórico operam
sempre na empresa da sessão, e um id manipulável pelo cliente simplesmente não
existe no contrato. `pagina_importar`, por sua vez, usa o usuário opcional e
redireciona ao login, mantendo a navegação não autenticada coerente com o resto
da aplicação.

**4. Falhas de importação viram rollback + resposta parcial HTMX**

`analisar()` levanta `ErroImportacao` (tipo desconhecido, arquivo vazio, colunas
ausentes) antes de qualquer escrita, mas a sessão pode carregar mudanças
pendentes; o rollback garante o invariante “arquivo inválido não altera dados”
(AC5). O erro é renderizado como fragmento em `importar_resultado.html`, no
próprio alvo do formulário, sem trocar de página — feedback imediato para o
admin, sem uma tela de erro genérica.

**5. Templates Jinja2 com autoescape e CSS no tema existente**

As expressões `{{ }}` são autoescapadas pelo Jinja por padrão, o que mitiga XSS
ao exibir `erro`/`motivo`/`tipo` vindos do usuário. O CSS entra em
`static/app.css` seguindo as variáveis `--cor-*` já usadas, de modo que a tela
nova herda o tema em vez de introduzir um estilo paralelo.

## 3. Concessões e Escolhas Práticas (Trade-offs)

- **Sessão síncrona dedicada em vez de reusar a assíncrona do auth:** a
  importação precisou de um segundo engine (sync) apontando para a mesma base,
  duplicando a configuração de conexão. Aceitável porque a T11/T12 são
  explicitamente síncronas e converter tudo para async seria um custo alto fora
  do MVP.
- **Conteúdo lido integralmente em memória** (`arquivo.file.read()`), sem limite
  de tamanho. Suficiente para os CSVs do MVP (grandes, porém finitos); um limite
  fica para iteração posterior.
- **`commit`/`rollback` controlados pelo handler**, não por um _unit of work_ do
  serviço: mantém a T12 intacta e o controle transacional explícito na fronteira
  web.
- **Sem proteção CSRF em `POST /importar`:** coerente com o restante da app
  (auth e onboarding também não têm), mas endpoints de mudança de estado
  protegidos só por cookie devem ganhar CSRF antes de produção.
- **Erros de banco inesperados** (não `ErroImportacao`, ex.: `IntegrityError`)
  resultam em 500 padrão, sem mensagem amigável e sem fuga de detalhes internos.
- **O engine síncrono sempre deriva de `get_settings()`:** o `lru_cache` ignora
  um `settings` customizado passado a `create_app`. Em produção a fonte é única
  e nos testes a sessão é sobrescrita por injeção, então não há impacto hoje.

## 4. O que vem a seguir (Roadmap Imediato)

- **T14/T15/T16/T34 (tools por tenant):** as tools de estoque, fornecedores e
  transporte passam a ler do banco por `empresa_id`, com as análises read-only; a
  T34 acrescenta a tool comum de resposta aos três especialistas.
- **T17 (Copilot Service):** o ponto em que as fábricas de tools por tenant são
  injetadas no grafo, ligando a importação ao copiloto.
- **T18/T19 (SSE e UI do chat):** o transporte e a tela que fecham a experiência
  do operador sobre os dados importados.

## 5. Validação de Qualidade e Segurança

- **Garantias de negócio e privacidade:** o histórico e o upload escopam sempre
  pela empresa da sessão; `test_historico_isola_por_empresa` prova que dados de
  um tenant não aparecem no outro. Arquivo inválido não grava nada, por causa do
  rollback.
- **Cobertura e testes automatizados:** `tests/web/test_ingestion_ui.py` cobre o
  redirect sem sessão, a renderização do formulário, o upload válido (com
  gravação verificada no repositório), a linha inválida reportada por linha, o
  arquivo de tipo desconhecido, o histórico preenchido, o histórico vazio e o
  isolamento por empresa.
- **Padrões de qualidade:** Jinja com autoescape em todas as expressões; `black`
  e `ruff` aplicados aos arquivos do módulo web.
