# ADR: t17-copilot-service

## 1. Context & Goal

A T17 implementa COP-01/COP-02: um serviço que **injeta o contexto do tenant** nas
tools, roda o grafo supervisor + especialistas e devolve a resposta, com modelo
injetável para teste (fake). É a costura entre o caminho mock do REPL/CLI e o
caminho por tenant das T14/T15/T16/T34. O desafio técnico não é algoritmo: é abrir
um **seam de injeção** das fábricas (`build_inventory_tools` / `build_supplier_tools`
/ `build_transport_tools`) sem quebrar o contrato atual dos builders, nem o REPL,
nem os testes, e extrair a resposta final do estado do grafo de forma robusta —
tratando o caso "fora de escopo". A F1 é read-only (AD-001).

## 2. Architectural Decisions

- **Decision 1:** os builders dos especialistas ganharam um 3º parâmetro opcional
  `tools: Sequence[BaseTool] | None = None`; quando omitido, usa o mock `TOOLS`.
  - **Justification:** preserva **exatamente** o contrato anterior
    (`build_*_node(model, max_steps)`) — REPL, `graph.build_graph` sem injeção e
    os testes existentes continuam funcionando — e abre o ponto de injeção sem
    duplicar builders. `base = TOOLS if tools is None else tools` distingue
    "não injetado" (mock) de "injetado" de forma explícita; uma sequência vazia
    válida é respeitada (só `COMMON_TOOLS`), evitando surpresas de truthiness.
- **Decision 2:** `build_graph(..., specialist_tools: Mapping[str, Sequence[BaseTool]]
  | None = None)`, indexado por **nome do especialista** (`"estoque"`,
  `"fornecedores"`, `"transporte"`) com `ferramentas.get(<nome>)` por nó.
  - **Justification:** um único seam de injeção no nível do grafo, sem mutar as
    sequências recebidas e sem acoplar o `CopilotService` à ordem de criação dos
    nós. A ausência do mapa (ou de uma chave) cai no mock do domínio, mantendo a
    compatibilidade total. As chaves são o mesmo contrato de `SPECIALISTS`/`Route`
    (`state.py`), evitando strings divergentes.
- **Decision 3:** a `COMMON_TOOLS` é anexada **dentro do builder**
  (`[*base, *COMMON_TOOLS]`), não mais no ponto de composição do nó.
  - **Justification:** a tool comum **não é tenant-scoped** (T34) e não deve entrar
    no closure das fábricas; anexá-la no builder garante que ela continue no
    binding dos três especialistas independentemente do que foi injetado. A
    invariante da T34 (comum sempre presente) fica em um só lugar, e o splat cria
    lista nova a cada chamada, sem mutar `TOOLS`/`COMMON_TOOLS`.
- **Decision 4:** `CopilotService` é um `@dataclass(frozen=True)` com `session`,
  `empresa_id`, `model` e `settings`, e constrói as tools **por chamada** em
  `tools_por_dominio()`, passando os repositórios já escopados.
  - **Justification:** imutabilidade do handle do serviço evita reatribuição
    acidental de sessão/tenant durante a vida do objeto; a construção por chamada
    (repositórios + closures) é o que garante que o `empresa_id` correto esteja
    amarrado às tools daquela requisição, sem cache global que vazaria entre
    tenants. O `model` injetável é o que permite testar sem rede/Ollama
    (`conftest.fake_model_cls`).
- **Decision 5:** `answer()` resolve a configuração uma única vez
  (`resolvido = self.settings or get_settings()`) e reusa o mesmo objeto para
  construir o grafo **e** para o `recursion_limit` do `run_query`.
  - **Justification:** evita divergência entre o `recursion_limit` efetivo do grafo
    (que resolveria `get_settings()` quando `settings is None`) e o passado ao
    `run_query`. Remove o número mágico `_LIMITE_RECURSAO_PADRAO = 25`, fazendo o
    serviço respeitar `RECURSION_LIMIT` do ambiente também no caminho sem
    `settings` explícito.
- **Decision 6:** `_texto_resposta` varre o estado de trás para frente e devolve a
  última `AIMessage` com conteúdo não vazio; se não houver, devolve
  `MENSAGEM_FORA_DE_ESCOPO`.
  - **Justification:** os especialistas devolvem apenas a resposta final ao estado
    pai (`create_specialist_node` não vaza `ToolMessage`), então a última
    `AIMessage` é a resposta do domínio. O supervisor roteia via
    `with_structured_output` e não adiciona texto de assistente; quando a rota é
    `FINISH` sem especialista, não há `AIMessage` → mensagem de fora de escopo. O
    filtro por `content` não vazio cobre o caso de um `AIMessage` vazio (tool call
    sem texto) sem devolver string vazia.
- **Decision 7 (correção de ponteiro):** o ponto de injeção das fábricas por tenant
  é a **T17**, não a T19 (como registrado nas ADRs das T14/T15/T16/T34).
  - **Justification:** a T17 é quem tem sessão + `empresa_id` e monta as tools; a
    T18/T19 (SSE/UI) apenas consomem o serviço. O mock `TOOLS` **permanece** como
    fallback do REPL (`cli.py`) até a interface web/CLI receber DB; portanto a
    ação original "injetar fábricas **e remover mock**" se partiu em duas: a
    injeção é a T17, a remoção do mock fica para a migração do REPL. Os ponteiros
    nas ADRs T14/T15/T16/T34 e nas docstrings de `tools/*.py` foram corrigidos.

## 3. Trade-offs & Compromises

- **Resposta como `str` simples**, sem estrutura de recomendação/fontes. Aceitável:
  a estruturação é explicitamente escopo da T21 (`copilot/`, COP-03/COP-04); a T17
  entrega o canal de execução com contexto de tenant.
- **Sem streaming/SSE e sem persistência:** a T17 roda o grafo de forma síncrona e
  devolve a resposta completa. SSE é T18 e histórico é T20; manter a T17 focada evita
  acoplar o serviço ao transporte HTTP.
- **Fábricas re-construídas a cada `answer()`** (serviço também por requisição).
  Custo de construção baixo e prematuro otimizar; a construção por requisição é o
  que garante a tenancy correta das closures.
- **`TOOLS` mock e fábrica coexistem:** o REPL continua no mock. É a ponte
  deliberada até a interface receber DB; o risco de uso acidental está documentado
  como ação pendente (pós-T17), não como bloqueio.
- **`empresa_id` inexistente não gera erro:** as tools do tenant respondem
  "não encontrado" e o serviço devolve a resposta do modelo. Aceitável para um
  caminho read-only; validação/404 é da camada web (T18).

## 4. Known Limitations

- **Sem redação de PII, medição de tokens e persistência** — a T17 é só o canal;
  AD-001 mantém a F1 read-only e esses itens entram nas tasks seguintes.
- **Sem checagem de existência do tenant:** `answer()` de uma empresa inexistente
  devolve a resposta sem dados, não um erro de domínio.
- **`GraphRecursionError` propaga:** se um especialista nunca devolver `FINISH`, o
  grafo estoura `recursion_limit` (gotcha do AGENTS.md). Tratamento/degradação é
  responsabilidade das camadas T18+.
- **`_texto_resposta` usa `str(mensagem.content)`:** conteúdo multimodal (lista de
  blocos) viraria uma representação textual; no MVP o conteúdo é texto simples.
- **Ciclo de vida da sessão é do chamador:** o serviço não faz `commit`/`rollback`
  nem fecha a sessão; quem monta o serviço (T18) é dono do escopo transacional.

## O que fica para T18–T22

- **T18 (SSE):** endpoint autenticado que cria o `CopilotService` da sessão e
  transmite a resposta em streaming; 401 sem sessão.
- **T19 (UI do chat):** tela HTMX/SSE consumindo o endpoint.
- **T20 (histórico):** persistência de conversa/mensagens por usuário/tenant.
- **T21 (recomendação/fontes/insuficiência):** estruturação da resposta
  (`Recommendation`, `fontes`, dado insuficiente) sobre a saída da T17.
- **T22 (feedback):** aceitar/descartar persistido por tenant.
- **Migração do REPL:** remoção dos `TOOLS` mock de `inventory.py`/`suppliers.py`/
  `transport.py` ao conectar o REPL ao DB (ação das ADRs T14/T15/T16/T34,
  agora com ponteiro corrigido).

## Achados corrigidos no self-review

- **Divergência de `recursion_limit`:** quando `settings=None`, o grafo era
  construído com `get_settings()` (respeitando `RECURSION_LIMIT` do ambiente), mas
  o `run_query` usava o número mágico `_LIMITE_RECURSAO_PADRAO = 25`. Corrigido
  para resolver a config uma vez (`self.settings or get_settings()`) e usar
  `resolvido.recursion_limit` nos dois pontos; a constante foi removida.
- **Ponteiro T19→T17 corrigido** nas docstrings de `tools/inventory.py`,
  `tools/suppliers.py` e `tools/transport.py` e nas ADRs T14/T15/T16/T34, com a
  nota de que o mock `TOOLS` permanece como fallback do REPL até a web/CLI receber
  DB.
- **Sem achados de tenant/segurança:** cada tool usa operações escopadas por
  `empresa_id`; `test_tools_do_tenant_isola_entre_empresas` prova que a mesma
  `SKU-1` de outro tenant não vaza, e `test_answer_injeta_contexto_do_tenant` prova
  que a injeção chega ao nó (`bound_tools` do fake).
- **Contrato dos builders preservado:** o default `tools=None` mantém o mock e os
  testes de especialistas/grafo existentes passam sem alteração; `build_graph` sem
  `specialist_tools` segue idêntico ao comportamento anterior.
- **Sem mutação/compartilhamento:** `[*base, *COMMON_TOOLS]` cria lista nova no
  builder e `create_specialist_node` copia com `list(tools)`; `specialist_tools` é
  apenas lido via `.get()`.
- **Cobertura T17:** 5 testes em `tests/copilot/test_service.py` (roteia nos 3
  domínios, fora de escopo, injeta contexto do tenant, isola entre empresas,
  empresa sem dados) com `copilot/service.py` em 100%.
- Gate final: `pytest` -> 120 passed, cobertura 97.36%; `black --check` -> 68 files
  unchanged; `ruff check` -> All checks passed.
