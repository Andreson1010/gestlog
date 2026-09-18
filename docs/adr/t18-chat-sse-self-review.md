# ADR: t18-chat-sse

## 1. Contexto & Objetivo

A T17 entregou o motor do copiloto, mas ele só era alcançável de dentro do
processo. A T18 fecha o caminho web (COP-01, critério 5; COP-05): uma rota
**autenticada** que recebe a pergunta do operador e transmite a resposta por
**SSE**, reusando o `CopilotService` da T17, que já injeta o contexto do tenant e
roda o grafo. A T7 entra como dependência de autenticação e tenancy. O desafio
técnico não é o algoritmo de resposta — é a **costura HTTP**: resolver o tenant
da sessão, escolher um formato de transporte que funcione com HTMX/EventSource,
validar a entrada e manter a fábrica de modelo testável sem rede. A F1 é
read-only (AD-001), então a rota só lê e responde.

## 2. Decisões de Arquitetura

**1. A resposta é transmitida como um evento com o texto final, não token a token**

O endpoint emite `event: resposta` seguido de `event: fim`, com o texto completo
do especialista. A T17 devolve `str` e não expõe um iterador do grafo; streaming
token a token exigiria mudar o contrato de `CopilotService.answer`, o que é
escopo de outra task. O design da F1 registra a pergunta aberta 4 (token a token
vs. resposta final por SSE) e optou-se pela resposta final, que já satisfaz o
critério “transmiti-la em streaming (SSE)” do ponto de vista do transporte, sem
reescrever a T17. Eventos nomeados dão à UI da T19 um contrato estável e
extensível — basta acrescentar `event: erro`/`event: token` depois.

**2. `GET /chat/stream?pergunta=...` com `Query(min_length=1)`**

É o formato que `EventSource` e a extensão SSE do HTMX (`sse-connect`) consomem
nativamente, sem JavaScript extra para enviar body em POST. O `min_length=1`
rejeita a pergunta vazia na borda (422) antes de acionar o LLM/grafo, evitando
custo e execução sem entrada, e preserva o contrato da T17: o endpoint só chama
`answer(pergunta)`.

**3. Sem sessão, o endpoint responde 401 — não o redirect das páginas HTML**

A dependência `get_current_empresa` (FastAPI Users) garante o 401 e resolve a
**tenancy** da sessão (`empresa.id`), de modo que as tools sejam escopadas ao
tenant do usuário e não a um id vindo do cliente. Um redirect seria pior num
endpoint de API/SSE: um `EventSource`/fetch o seguiria silenciosamente e
entregaria o HTML de login como se fosse o stream. O 401 é o sinal correto para a
T19 distinguir “não autenticado” de “resposta”.

**4. `get_chat_model` é uma dependência injetável e memoizada**

A rota recebe o modelo por `Depends(get_chat_model)`, com `lru_cache` sobre
`build_chat_model`. Isso permite `dependency_overrides` nos testes (modelo fake,
sem rede/Ollama) e evita reconstruir o `ChatOpenAI` por requisição, que é o
objeto mais caro da rota. O `lru_cache` é seguro porque `ChatOpenAI` é stateless
para `invoke`/`bind_tools`/`with_structured_output` — estes devolvem runnables
novos, sem mutar a instância base.

**5. O payload é quebrado em linhas `data:`, sem JSON**

`_evento` formata cada frame quebrando o texto em linhas `data:` e fechando com
linha em branco, exatamente o formato do EventSource. Isso evita que o cliente da
T19 precise fazer `JSON.parse` e lida com resposta multi-linha sem quebrar o
frame (cada linha vira um `data:` e o cliente recompõe com `\n`). O
`splitlines() or [""]` garante frame válido mesmo para resposta vazia.

**6. A rota é síncrona (`def`), com sessão sync para as tools e async só no auth**

`CopilotService.answer`/`run_query` são bloqueantes; um `async def` bloquearia o
event loop. Como `def`, o FastAPI a executa no threadpool. Mantém-se a separação
já usada na ingestão (auth assíncrono, ferramentas síncronas) e o mesmo
`get_sync_session` é reutilizado, evitando uma segunda fábrica de engine.

## 3. Concessões e Escolhas Práticas (Trade-offs)

- **“Streaming” entrega a resposta em um único evento**, sem latência
  incremental percebida. Aceitável: o done-when da T18 é “SSE emite a resposta”;
  token a token é otimização de p95 percebida e pode ser adicionado depois sem
  quebrar o contrato de eventos.
- **A resposta é calculada antes do `StreamingResponse` existir:** a pergunta é
  respondida por completo antes do primeiro byte. Quando o streaming real entrar,
  `answer` precisará virar gerador sobre o grafo.
- **Pergunta na query string (GET):** fica registrada em logs de acesso.
  Aceitável em HTTP local/temporário; o endpoint é autenticado e a redação de PII
  é a T24/T25 — anotado como limitação.
- **Sessão síncrona e assíncrona na mesma requisição:** duas conexões ao banco
  (uma para auth/tenancy, uma para as tools), padrão já existente na ingestão;
  unificar seria refatoração da T17/T7, fora do escopo.
- **`get_chat_model` compartilhado entre requisições/tenants:** não carrega
  estado de tenant (as tools é que são escopadas por requisição), então não há
  vazamento; coberto pela tenancy das closures da T17.
- **`get_sync_session` vive em `ingestion_ui.py`** e é importado por `chat.py`;
  o lugar conceitual seria um `web/deps.py`. Débito pequeno, mantido para não
  mexer na ingestão/T13.
- **Sem tratamento de exceção do grafo:** `GraphRecursionError`/erro do LLM antes
  do stream vira 500 e nenhum evento é emitido; a degradação é responsabilidade
  das camadas T18+, mantendo o comportamento simples (sem `event: erro`) por
  escopo.

## 4. O que vem a seguir (Roadmap Imediato)

- **T19 (UI do chat):** a tela consome `GET /chat/stream` via `sse-connect`,
  escuta `event: resposta`/`event: fim` e renderiza a resposta; trata 401/redirect
  de login.
- **T20 (persistência/histórico):** gravar conversa/mensagens por
  usuário/tenant e recuperar ao voltar — hoje o endpoint não persiste nada.
- **T21 (recomendação/fontes/insuficiência):** estruturar a resposta
  (`Recommendation`, `fontes`, dado insuficiente) sobre a saída da T17; o
  contrato de eventos da T18 foi desenhado para acomodar novos eventos.

## 5. Validação de Qualidade e Segurança

- **Garantias de negócio e privacidade:** `get_current_empresa` garante 401 sem
  sessão e resolve o `empresa_id` do vínculo da sessão — nenhuma query usa id de
  parâmetro. A pergunta é validada (`Query(min_length=1)`) antes de tocar o
  grafo, e `Cache-Control: no-cache` evita cache intermediário do stream.
- **Cobertura e testes automatizados:** 5 testes de integração cobrem o 401 sem
  sessão, a emissão de `resposta`/`fim`, o fora de escopo e o 422 de pergunta
  vazia, com `web/chat.py` em 100%. Gate final: `pytest` → 125 passed, cobertura
  97.43%; `black --check` → 70 files unchanged; `ruff check` → All checks passed.
- **Padrões de qualidade:** `_evento` emite frames `event:`/`data:` válidos e
  fecha com linha em branco; `get_chat_model`, `get_sync_session` e `get_settings`
  são dependências sobrescrevíveis, e nenhum teste toca rede/Ollama.

## Achados corrigidos no self-review

- **Nada a corrigir no código.** A revisão do diff (auth/401, tenancy, validação
  de entrada, formato SSE, injeção de dependência, cobertura e riscos) não
  encontrou achados que exigissem edição.

## Nota de limitação

- **Sem streaming token a token** e sem heartbeat/keep-alive SSE para conexões
  ociosas longas; proxies com buffering podem atrasar a entrega.
- **`pergunta` só valida tamanho**, não conteúdo: uma pergunta só com espaços
  passa. Validação semântica fica fora do MVP.
- **Sem persistência/histórico:** cada requisição é stateless (`answer` novo);
  histórico é a T20.
