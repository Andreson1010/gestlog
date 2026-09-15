# ADR: t18-chat-sse

## 1. Context & Goal

A T18 fecha o caminho web do copiloto (COP-01, critério 5; COP-05): uma rota
**autenticada** que recebe a pergunta do operador e transmite a resposta por
**SSE**, reusando o `CopilotService` da T17 (que já injeta o contexto do tenant e
roda o grafo). A T7 entra como dependência de autenticação/tenancy. O desafio
técnico não é o algoritmo de resposta — é a **costura HTTP**: resolver o tenant
da sessão, escolher um formato de transporte que funcione com HTMX/EventSource,
validar a entrada e manter a fábrica de modelo testável sem rede. A F1 é
read-only (AD-001).

## 2. Architectural Decisions

- **Decision 1:** a resposta é transmitida como **um evento com o texto final**
  (`event: resposta` + `event: fim`), não token a token.
  - **Justification:** a T17 devolve `str` completo e não expõe um iterador do
    grafo; o streaming token a token exigiria mudar o contrato de
    `CopilotService.answer` (task de escopo diferente). O design do F1 registra
    a pergunta aberta 4 (token a token vs. resposta final por SSE); optou-se pela
    resposta final, que já satisfaz o critério "transmiti-la em streaming (SSE)"
    do ponto de vista do transporte, com custo mínimo e sem reescrever a T17.
    Eventos nomeados (`resposta`/`fim`) dão à T19 (UI) um contrato estável e
    extensível (basta adicionar `event: erro`/`event: token` depois).
- **Decision 2:** `GET /chat/stream?pergunta=...` com `Query(min_length=1)`.
  - **Justification:** é o formato que `EventSource` e a extensão SSE do HTMX
    (`sse-connect`) consomem nativamente, sem JS extra para body em POST. O
    `min_length=1` rejeita a pergunta vazia na borda (422) antes de acionar o
    LLM/grafo, evitando custo e execução sem entrada. Preserva o contrato da
    T17: o endpoint só chama `answer(pergunta)`.
- **Decision 3:** sem sessão o endpoint responde **401**, via dependência
  `get_current_empresa` (FastAPI Users), e não o redirect 303 usado nas páginas
  HTML.
  - **Justification:** é um **endpoint de API/SSE**; um redirect seria seguido
    silenciosamente por um `EventSource`/fetch, entregando o HTML de login como
    se fosse o stream. O 401 é o sinal correto para o cliente da T19 distinguir
    "não autenticado" de "resposta". `get_current_empresa` também resolve a
    **tenancy** da sessão (`empresa.id`), garantindo que as tools sejam escopadas
    ao tenant do usuário, não a um id vindo do cliente.
- **Decision 4:** `get_chat_model` é uma **dependência injetável** (`lru_cache`,
  `build_chat_model`), consumida com `Depends`.
  - **Justification:** permite `dependency_overrides` nos testes (modelo fake,
    sem rede/Ollama) e evita reconstruir o `ChatOpenAI` por requisição, que é
    o objeto mais caro da rota. O `lru_cache` é seguro aqui porque `ChatOpenAI`
    é stateless para `invoke`/`bind_tools`/`with_structured_output` (estes
    devolvem runnables novos, sem mutar a instância base).
- **Decision 5:** o payload é quebrado em **linhas `data:`** por `_evento`, em
  vez de empacotar JSON.
  - **Justification:** é exatamente o formato do EventSource/SSE; evita ao
    cliente da T19 fazer `JSON.parse` e lida com resposta multi-linha sem
    quebrar o frame (cada linha vira um `data:` e o cliente recompõe com `\n`).
    O separador em branco ao final fecha o evento, e `splitlines() or [""]`
    garante frame válido mesmo para resposta vazia.
- **Decision 6:** a rota é **síncrona** (`def`), com `get_sync_session` para as
  tools e `get_async_session` (via `get_current_empresa`) só no auth.
  - **Justification:** `CopilotService.answer`/`run_query` são bloqueantes; um
    `async def` bloquearia o event loop. Como `def`, o FastAPI a executa no
    threadpool, sem travar o servidor. Mantém a separação já usada na ingestão
    (auth assíncrono, ferramentas síncronas) — o mesmo `get_sync_session` é
    reutilizado, evitando uma segunda fábrica de engine.

## 3. Trade-offs & Compromises

- **"Streaming" entrega a resposta em um único evento** (sem latência
  incremental percebida). Aceitável: o done-when da T18 é "SSE emite a resposta";
  token a token é otimização de p95 percebida e pode ser adicionada depois sem
  quebrar o contrato de eventos. A pergunta aberta 4 do design segue registrada.
- **A resposta é calculada antes do `StreamingResponse` existir:** a pergunta é
  respondida por completo antes do primeiro byte. Aceitável no MVP; quando o
  streaming real entrar, o `answer` precisará virar gerador sobre o grafo.
- **Pergunta vai na query string (GET):** fica registrada em logs de acesso.
  Aceitável em HTTP local/temporário; o endpoint é autenticado e a redação de
  PII é a T24/T25 — anotado como limitação.
- **Sessão síncrona + sessão assíncrona na mesma requisição:** duas conexões ao
  banco (uma para auth/tenancy, uma para as tools). É o padrão já existente
  (ingestão) e mantém o `CopilotService` síncrono; unificar seria refatoração da
  T17/T7, fora do escopo.
- **`get_chat_model` compartilhado entre requisições/tenants:** não carrega
  estado de tenant (as tools é que são escopadas por requisição), então não há
  vazamento. Aceitável e coberto pela tenancy das closures da T17.

## 4. Known Limitations

- **Sem streaming token a token** e sem heartbeat/keep-alive SSE para conexões
  ociosas longas — a resposta chega completa; proxies com buffering podem
  atrasar a entrega. Revisitar quando o streaming real for implementado.
- **Sem tratamento de exceção do grafo:** `GraphRecursionError`/erro do LLM
  antes do stream vira 500 e nenhum evento é emitido. A T17 já documenta que a
  degradação é responsabilidade das camadas T18+; a T18 mantém o comportamento
  simples (sem `event: erro`) por escopo.
- **`pergunta` só valida tamanho**, não conteúdo: uma pergunta só com espaços
  (`min_length=1` após URL-encoding) passa. Validação semântica/normalização não
  faz parte do MVP.
- **`get_sync_session` vive em `ingestion_ui.py`** e é importado por `chat.py`;
  o lugar conceitual de uma dependência compartilhada de sessão seria um
  `web/deps.py`. Débito pequeno, mantido para não churnar a ingestão/T13.
- **Sem persistência/histórico:** cada requisição é stateless (`answer` novo).
  Histórico é a T20.

## O que fica para T19–T21

- **T19 (UI do chat, HTMX/SSE):** a tela consome `GET /chat/stream` via
  `sse-connect`, escuta `event: resposta`/`event: fim` e renderiza a resposta;
  trata 401/redirect de login.
- **T20 (persistência/histórico):** gravar conversa/mensagens por
  usuário/tenant e recuperar ao voltar — hoje o endpoint não persiste nada.
- **T21 (recomendação/fontes/insuficiência):** estruturar a resposta
  (`Recommendation`, `fontes`, dado insuficiente) sobre a saída da T17; o
  contrato de eventos da T18 foi desenhado para acomodar novos eventos.

## Achados corrigidos no self-review

- **Nada a corrigir no código.** A revisão do diff (auth/401, tenancy,
  validação de entrada, formato SSE, injeção de dependência, cobertura e riscos)
  não encontrou achados que exigissem edição:
  - **Auth/401:** `get_current_empresa` (dependência de `current_active_user`)
    garante 401 sem sessão; teste de integração cobre o caminho.
  - **Tenancy:** o `empresa_id` vem do vínculo da sessão, nunca do cliente;
    nenhuma query usa id de parâmetro.
  - **Validação:** `Query(min_length=1)` rejeita pergunta vazia (422) antes de
    tocar o grafo.
  - **SSE:** `_evento` emite frames `event:`/`data:` válidos e fecha com linha
    em branco; `Cache-Control: no-cache` evita cache intermediário.
  - **Injeção:** `get_chat_model`, `get_sync_session` e `get_settings` são
    dependências sobrescrevíveis; os testes não tocam rede/Ollama.
  - **Cobertura:** `web/chat.py` em 100% (5 testes de integração).
- Gate final: `pytest` -> 125 passed, cobertura 97.43% (gate 80%);
  `black --check` -> 70 files unchanged; `ruff check` -> All checks passed.
