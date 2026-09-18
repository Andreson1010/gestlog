# ADR: t17-copilot-service

## 1. Contexto & Objetivo

Até a T17 havia dois mundos separados: o REPL e os testes rodavam o grafo com
tools mockadas, e as T14/T15/T16/T34 já tinham construído fábricas capazes de ler
os dados reais de cada empresa. Faltava a ponte. A T17 implementa COP-01/COP-02:
um serviço que **injeta o contexto do tenant** nas tools, roda o grafo
supervisor + especialistas e devolve a resposta, com o modelo injetável para
teste sem rede. O desafio não é algorítmico — é abrir um **seam de injeção** para
as fábricas (`build_inventory_tools`, `build_supplier_tools`,
`build_transport_tools`) sem quebrar o contrato atual dos builders, nem o REPL,
nem os testes, e extrair a resposta final do estado do grafo de forma robusta,
inclusive no caso “fora de escopo”. A F1 é read-only (AD-001), então o serviço só
lê e responde.

## 2. Decisões de Arquitetura

**1. Terceiro parâmetro opcional `tools` nos builders**

Cada builder de especialista ganhou `tools: Sequence[BaseTool] | None = None`;
quando omitido, usa o mock `TOOLS`. Isso preserva **exatamente** o contrato
anterior (`build_*_node(model, max_steps)`) — o REPL, o `build_graph` sem injeção
e os testes existentes continuam funcionando — e abre o ponto de injeção sem
duplicar builders. A distinção é explícita (`base = TOOLS if tools is None else
tools`): “não injetado” usa o mock, e uma sequência vazia legítima é respeitada
(só `COMMON_TOOLS`), sem surpresas de truthiness.

**2. `build_graph(..., specialist_tools=...)` indexado pelo nome do especialista**

Um único seam de injeção no nível do grafo, com as chaves `"estoque"`,
`"fornecedores"` e `"transporte"` resolvidas por `ferramentas.get(<nome>)` em
cada nó. Isso não muta as sequências recebidas nem acopla o `CopilotService` à
ordem de criação dos nós; a ausência do mapa (ou de uma chave) cai no mock do
domínio, mantendo compatibilidade total. As chaves são o mesmo contrato de
`SPECIALISTS`/`Route` (`state.py`), o que evita strings divergentes entre grafo e
serviço.

**3. A `COMMON_TOOLS` é anexada dentro do builder**

A tool comum **não é tenant-scoped** (T34) e não deve entrar no closure das
fábricas; anexá-la em `[*base, *COMMON_TOOLS]` garante que ela continue no
binding dos três especialistas independentemente do que foi injetado. A
invariante da T34 — comum sempre presente — fica em um só lugar, e o splat cria
lista nova a cada chamada, sem mutar `TOOLS`/`COMMON_TOOLS`.

**4. `CopilotService` como `@dataclass(frozen=True)` que constrói tools por chamada**

O serviço guarda `session`, `empresa_id`, `model` e `settings`; a imutabilidade
do handle evita reatribuição acidental de sessão/tenant durante sua vida, e
`tools_por_dominio()` constrói as ferramentas por chamada, passando os
repositórios já escopados. É essa construção por requisição — sem cache global —
que garante que o `empresa_id` correto esteja amarrado às closures daquela
requisição, sem vazar entre tenants. O `model` injetável é o que permite testar
com `conftest.fake_model_cls`, sem tocar rede/Ollama.

**5. `answer()` resolve a configuração uma única vez**

`answer()` faz `resolvido = self.settings or get_settings()` e reusa o mesmo
objeto para construir o grafo **e** para o `recursion_limit` do `run_query`. Isso
remove a divergência possível entre o limite efetivo do grafo e o passado à
invocação, e elimina o número mágico `_LIMITE_RECURSAO_PADRAO = 25`: o serviço
passa a respeitar `RECURSION_LIMIT` do ambiente também quando nenhum `settings`
explícito é dado.

**6. `_texto_resposta` varre o estado de trás para frente**

A função devolve a última `AIMessage` com conteúdo não vazio; se não houver,
devolve `MENSAGEM_FORA_DE_ESCOPO`. Como `create_specialist_node` devolve apenas a
resposta final ao estado pai (sem `ToolMessage` intermediário), a última
`AIMessage` é a resposta do domínio. O supervisor roteia via
`with_structured_output` e não adiciona texto de assistente; quando a rota é
`FINISH` sem especialista, não há `AIMessage` — daí a mensagem de fora de escopo.
O filtro por conteúdo não vazio cobre um `AIMessage` sem texto (tool call) sem
devolver string vazia.

**7. Correção de ponteiro: a injeção é T17, não T19**

As ADRs das T14/T15/T16/T34 apontavam a injeção das fábricas para a T19; na
verdade é a **T17** quem tem sessão + `empresa_id` e monta as tools, enquanto a
T18/T19 apenas consomem o serviço. A ação original “injetar fábricas e remover
mock” se partiu em duas: a injeção é a T17, a remoção do mock fica para a
migração do REPL. Os ponteiros nas ADRs e nas docstrings de `tools/*.py` foram
corrigidos.

## 3. Concessões e Escolhas Práticas (Trade-offs)

- **Resposta como `str` simples**, sem estrutura de recomendação/fontes. A
  estruturação é explicitamente escopo da T21 (`copilot/`, COP-03/COP-04); a T17
  entrega o canal de execução com contexto de tenant.
- **Sem streaming/SSE e sem persistência:** o grafo roda de forma síncrona e
  devolve a resposta completa. SSE é T18 e histórico é T20 — manter o serviço
  focado evita acoplá-lo ao transporte HTTP.
- **Fábricas reconstruídas a cada `answer()`**, como o próprio serviço. Custo
  baixo e prematuro otimizar; a reconstrução por requisição é o que garante a
  tenancy correta.
- **`TOOLS` mock e fábrica coexistem:** o REPL continua no mock, ponte deliberada
  até a interface receber banco; o risco de uso acidental é ação pendente
  (pós-T17), não bloqueio.
- **`empresa_id` inexistente não gera erro:** as tools do tenant respondem “não
  encontrado” e o serviço devolve a resposta do modelo. Para um caminho read-only
  é aceitável; validação/404 é da camada web (T18).
- **Ciclo de vida da sessão é do chamador:** o serviço não faz
  `commit`/`rollback` nem fecha a sessão; quem o monta (T18) é dono do escopo
  transacional.
- **`_texto_resposta` usa `str(mensagem.content)`:** conteúdo multimodal (lista
  de blocos) viraria representação textual; no MVP o conteúdo é texto simples.

## 4. O que vem a seguir (Roadmap Imediato)

- **T18 (SSE):** endpoint autenticado que cria o `CopilotService` da sessão e
  transmite a resposta; 401 sem sessão.
- **T19 (UI do chat):** tela HTMX/SSE consumindo o endpoint.
- **T20 (histórico):** persistência de conversa/mensagens por usuário/tenant.
- **T21 (recomendação/fontes/insuficiência):** estruturação da resposta
  (`Recommendation`, `fontes`, dado insuficiente) sobre a saída da T17.
- **T22 (feedback):** aceitar/descartar persistido por tenant.
- **Migração do REPL:** remoção dos `TOOLS` mock de `inventory.py`/`suppliers.py`/
  `transport.py` quando o REPL ganhar banco — a ação das ADRs T14/T15/T16/T34,
  agora com ponteiro corrigido.

## 5. Validação de Qualidade e Segurança

- **Garantias de negócio e privacidade:** cada tool usa operações escopadas por
  `empresa_id`; `test_tools_do_tenant_isola_entre_empresas` prova que a mesma
  `SKU-1` de outro tenant não vaza, e `test_answer_injeta_contexto_do_tenant`
  prova que a injeção chega ao nó (`bound_tools` do fake).
- **Cobertura e testes automatizados:** 5 testes em
  `tests/copilot/test_service.py` — roteia nos três domínios, fora de escopo,
  injeta contexto do tenant, isola entre empresas e empresa sem dados — com
  `copilot/service.py` em 100%. Gate `pytest` → 120 passed, cobertura 97.36%;
  `black --check` → 68 files unchanged; `ruff check` → All checks passed.
- **Compatibilidade preservada:** o default `tools=None` mantém o mock e os
  testes de especialistas/grafo passam sem alteração; `build_graph` sem
  `specialist_tools` segue idêntico ao comportamento anterior. Sem mutação
  compartilhada: `[*base, *COMMON_TOOLS]` cria lista nova no builder e
  `create_specialist_node` copia com `list(tools)`, enquanto `specialist_tools` é
  apenas lido via `.get()`.

## Achados corrigidos no self-review

- **Divergência de `recursion_limit`:** quando `settings=None`, o grafo era
  construído com `get_settings()` (respeitando `RECURSION_LIMIT`), mas o
  `run_query` usava `_LIMITE_RECURSAO_PADRAO = 25`. Corrigido para resolver a
  config uma vez e usar `resolvido.recursion_limit` nos dois pontos; a constante
  foi removida.
- **Ponteiro T19→T17 corrigido** nas docstrings de `tools/inventory.py`,
  `tools/suppliers.py` e `tools/transport.py` e nas ADRs T14/T15/T16/T34, com a
  nota de que o mock `TOOLS` permanece como fallback do REPL até a web/CLI
  receber banco.
- **Sem achados de tenant/segurança** além dos testes já citados.

## Nota de limitação

- **Sem redação de PII, medição de tokens e persistência** — a T17 é só o canal;
  AD-001 mantém a F1 read-only e esses itens entram nas tasks seguintes.
- **`GraphRecursionError` propaga:** se um especialista nunca devolver `FINISH`,
  o grafo estoura `recursion_limit` (gotcha do AGENTS.md). Tratamento/degradação
  é responsabilidade das camadas T18+.
