# ADR: t19-chat-ui

## 1. Contexto & Objetivo

A T18 fechou o caminho de dados do copiloto ao expor `GET /chat/stream?pergunta=`
como um stream SSE autenticado, mas deixou uma lacuna visível para o operador:
não havia tela alguma consumindo esse stream. A T19 resolve justamente a ponta
da experiência — o critério COP-01/COP-05 só se completa quando a pergunta
digitada e a resposta do especialista **aparecem na tela**, e não apenas trafegam
pela rede. O desafio arquitetural central não é renderizar HTML, e sim **costurar
três peças que já existem sem introduzir JavaScript próprio**: a autenticação de
página da T10 (redirect para `/login` quando não há sessão), o endpoint SSE da
T18 (que responde `401` porque é API) e a extensão oficial `htmx-ext-sse`, que
transforma uma `sse-connect` em uma assinatura de eventos no navegador. Cada uma
dessas peças tem um contrato diferente para "não autenticado" e para "fim de
stream", e a tela precisa respeitar todos eles.

## 2. Decisões de Arquitetura

**1. Separar a página inicial do turno dinâmico: `GET /chat` e `GET /chat/pergunta`**

A tela completa (`chat.html`, estendendo `base.html`) carrega apenas o formulário
e o contêiner vazio `#conversa`; cada submissão chama o fragmento
`GET /chat/pergunta`, que devolve só o turno recém-criado. Essa divisão é o que
permite ao HTMX anexar uma conversa cumulativa sem recarregar a página e sem
duplicar o shell de navegação/autenticação. O formulário usa `hx-get`,
`hx-target="#conversa"` e `hx-swap="beforeend"`, então o histórico visível cresce
por acréscimo. As duas rotas repetem o padrão já usado na ingestão: sem sessão,
`current_active_user_optional` devolve `None` e a resposta é um
`RedirectResponse` (`303`) para `/login` — o mesmo comportamento das demais
páginas HTML. O endpoint SSE da T18, por ser API, continua respondendo `401`,
preservando a distinção que a própria ADR anterior registrou.

**2. Consumir o stream com a extensão oficial, não com JavaScript proprietário**

O turno renderiza um `div.resposta` com `hx-ext="sse"`,
`sse-connect="/chat/stream?pergunta=..."` e `sse-swap="resposta"`. A extensão
`htmx-ext-sse@2.2.2` é carregada uma única vez em `base.html`, logo depois do
núcleo do HTMX, com `defer` e `integrity` (SRI). A alternativa — um
`EventSource` escrito à mão — exigiria tratar manualmente reconexão, remoção de
listeners e formatação de eventos, sem ganho algum; a extensão já faz isso de
forma testada pela comunidade. O contrato de eventos definido na T18
(`event: resposta` e `event: fim`) é exatamente o que `sse-swap`/`sse-close`
esperam, o que mantém as duas pontas desacopladas: a T21 pode acrescentar
`event: fontes` ou `event: erro` sem que a tela mude.

**3. O swap da resposta é texto, nunca HTML: `hx-swap="textContent"`**

Este foi o achado de segurança do self-review. A função interna da extensão faz
`api.getSwapSpecification(elt)` e delega a inserção ao mecanismo de swap do HTMX;
na ausência de `hx-swap`, o padrão é `innerHTML`. Como o conteúdo do evento nasce
da resposta do LLM — que pode ecoar a pergunta do operador ou dados de
ferramentas, e é, portanto, influenciável por prompt injection — um `innerHTML`
permitiria que um `<img src=x onerror=...>` contido na resposta fosse executado
no navegador de outro usuário do tenant. Declarar `hx-swap="textContent"` faz o
HTMX tratar o payload como texto puro: o HTML é exibido literalmente, sem
interpretação. É uma correção de uma linha que elimina a superfície de XSS
refletido/armazenado sem abrir mão do `white-space: pre-wrap` que preserva a
formatação da resposta.

**4. Encerrar a assinatura SSE no evento `fim`: `sse-close="fim"`**

O `EventSource` do navegador reconecta automaticamente quando o servidor fecha a
conexão, e o gerador da T18 termina o stream logo após emitir `event: fim`. Sem
uma instrução explícita, cada resposta concluída dispararia uma nova requisição a
`/chat/stream` — reexecutando o grafo, reacionando as tools e consumindo tokens
do LLM em ciclo, além de reescrever a bolha. A extensão oferece `sse-close`, que
registra um listener para o evento nomeado e fecha o `EventSource` quando ele
chega; com `sse-close="fim"`, o ciclo se encerra no contrato que a T18 já
publicava, sem alterar o endpoint.

**5. Codificação da pergunta na URL e escape no HTML**

A pergunta entra na tela por dois caminhos com necessidades distintas. No
`sse-connect`, ela é um valor de query string e passa pelo filtro `urlencode` do
Jinja, o que converte `&`, espaços e afins em sequências seguras — o teste cobre
`"frete & prazo"` virando `frete%20%26%20prazo`. Na bolha visível, `{{ pergunta }}`
é autoescapado pelo Jinja por padrão, de modo que caracteres como `<` não viram
markup. Nenhum dos dois caminhos usa `| safe`.

**6. Acessibilidade e ergonomia do formulário**

O contêiner `#conversa` recebe `aria-live="polite"`, para que leitores de tela
anunciem cada novo turno sem interromper o usuário; o campo mantém um `<label
for="pergunta">` associado, ganha `autofocus` e o formulário é limpo após cada
requisição com `hx-on::after-request="this.reset()"`, evitando que a pergunta
anterior permaneça no campo. Essas escolhas não alteram o fluxo de dados, mas
fazem a interação ser utilizável por teclado e tecnologia assistiva.

**7. Manter a fronteira `apps` intacta (AD-012)**

Todo o código novo vive em `src/gestlog/web/`: `chat_ui.py` (rotas), os templates
`chat.html`/`chat_turno.html` e o CSS. A UI não escreve SQL nem acessa modelo de
dados diretamente; ela apenas reusa o `get_sync_session` já exposto pela ingestão
e delega a resposta ao `CopilotService` por trás do endpoint da T18, que é quem
resolve a tenancy via `get_current_empresa`. Nenhuma dependência nova aponta de
`apps` para fora da direção permitida `apps → agents → libs`.

## 3. Concessões e Escolhas Práticas (Trade-offs)

- **A resposta chega em um único evento**: herda a decisão da T18 (resposta final
  por SSE, não token a token). A tela mostra "Consultando…" até o evento chegar,
  mas o ganho perceptível de latência incremental fica para quando o
  `CopilotService` expuser um iterador sobre o grafo. Aceitável porque o
  done-when da T19 é "pergunta e resposta aparecem via streaming na tela", e o
  transporte já é SSE.
- **Extensão SSE carregada em todas as páginas**: como `base.html` é compartilhado,
  o `sse.js` (~9 KB) é baixado também em telas que não usam streaming. Optou-se
  por isso em vez de criar um bloco `{% block scripts %}` agora, para manter o
  diff mínimo e o carregamento determinístico (HTMX antes da extensão). É um
  custo pequeno e reversível, registrado como candidato a otimização.
- **Dependência de terceiros via `unpkg` com SRI**: o hash `sha384` foi conferido
  durante o self-review contra o arquivo servido em `htmx-ext-sse@2.2.2`; a
  escolha evita vendorizar o JS no repositório, ao custo de depender de CDN. Se a
  política de rede do produto exigir self-hosting, é uma troca localizada.
- **Sem tratamento visual de sessão expirada com a tela aberta**: a navegação
  normal para `/chat` redireciona ao login, mas se a sessão vencer enquanto a
  tela está aberta, a `sse-connect` recebe `401` e o `EventSource` falha; o
  "Consultando…" permanece e a extensão tenta reconectar com backoff. Tratar isso
  exige um listener de `htmx:sseError` que redirecione ao login — comportamento
  que, sem um teste de navegador real, preferiu-se não introduzir às cegas nesta
  task. Fica como limitação conhecida (ver seção 4).
- **Formulário não é desabilitado durante o voo**: cliques repetidos anexam vários
  turnos. É aceitável no MVP read-only e evita um estado de "carregando" extra;
  pode ser refinado com `hx-disabled-elt` quando a UX for priorizada.

## 4. O que vem a seguir (Roadmap Imediato)

- **T20 (Persistência e histórico da conversa):** gravar pergunta e resposta por
  usuário/tenant e recarregar a conversa ao voltar à tela — hoje cada turno vive
  apenas no DOM e some no refresh.
- **T21 (Recomendação, fontes e insuficiência de dados):** estruturar a resposta
  (recomendação, fontes, aviso de dado insuficiente) e refletir isso na tela com
  novos eventos SSE, aproveitando que o contrato de eventos foi desenhado para
  acomodar `event: fontes` sem tocar no `sse-swap`.
- **T22/T23 (Feedback aceitar/descartar):** botões por turno para o operador
  registrar a decisão sobre a sugestão — o contêiner de conversa já é o ponto
  natural de extensão.
- **T24/T25 (PII, auditoria e uso):** redação de PII e telemetria, que hoje é a
  razão pela qual a pergunta viaja pela query string e aparece em logs de acesso.
- **Débito herdado:** extrair `get_sync_session` de `ingestion_ui.py` para um
  `web/deps.py`, hoje compartilhado por importação e chat; e avaliar a
  substituição do `unpkg` por assets servidos localmente.

## 5. Validação de Qualidade e Segurança

- **Garantias de negócio e privacidade:** a página `/chat` e o fragmento
  `/chat/pergunta` retornam `303` para `/login` sem sessão, e o endpoint de
  streaming mantém `401`, impedindo que o HTML de login seja tratado como stream.
  A tenancy continua resolvida pela sessão (`get_current_empresa`), nunca por
  parâmetro vindo do cliente, e o swap da resposta como texto bloqueia execução
  de HTML originado do LLM.
- **Cobertura e testes automatizados:** `tests/web/test_chat_ui.py` adiciona 6
  testes de integração (redirect sem sessão na página e no fragmento, render do
  formulário com `aria-live` e extensão SSE, assinatura `sse-connect` com
  `hx-swap`/`sse-close`, `urlencode` da pergunta e `422` para pergunta vazia).
  Suíte completa: **131 passed**, cobertura **97,48%** (gate de 80%), com
  `web/chat_ui.py` em **100%**.
- **Padrões de qualidade:** `uv run black --check src/ tests/` (72 arquivos
  inalterados) e `uv run ruff check src/ tests/` (All checks passed). O SRI da
  extensão SSE foi verificado bit a bit contra `htmx-ext-sse@2.2.2`.

## Achados corrigidos no self-review

- **XSS no swap da resposta (segurança):** o `div.resposta` herdava o swap padrão
  `innerHTML`; adicionado `hx-swap="textContent"` para tratar o payload como
  texto puro, eliminando a injeção de HTML vinda da resposta do LLM.
- **Reconexão do `EventSource` após o fim do stream (custo/duplicidade):**
  adicionado `sse-close="fim"` para encerrar a assinatura no evento de
  encerramento da T18, evitando reexecução do grafo e do LLM a cada resposta.
- **Acessibilidade do streaming:** `#conversa` ganhou `aria-live="polite"` para
  anunciar novos turnos a leitores de tela.
- **Ergonomia do formulário:** `autofocus` no campo e
  `hx-on::after-request="this.reset()"` para limpar a pergunta após o envio.
- **Higiene do fragmento:** removido o espaço em branco inicial de
  `chat_turno.html` e ajustada a indentação do contêiner em `chat.html`.
- **Cobertura dos novos atributos:** os testes passaram a verificar
  `hx-swap="textContent"`, `sse-close="fim"` e `aria-live="polite"`.
