# ADR: t34-common-response

## 1. Contexto & Objetivo

Os três especialistas precisavam de uma forma padronizada de fechar a resposta ao
operador, em vez de cada domínio inventar o próprio formato de entrega. A T34
introduz a tool comum do catálogo F1 (AD-010, design.md:178-181),
`enviar_resposta_logistica`, compartilhada por estoque, fornecedores e
transporte, com fonte única em `src/gestlog/tools/common.py`. O desafio não é
algoritmo — não há I/O — e sim decidir **onde** a tool mora e **como** ela se
combina com as tools de domínio sem duplicação e sem contaminar o escopo por
tenant que as T14/T15/T16 acabaram de estabelecer. A F1 é read-only (AD-001): a
tool apenas compõe o texto final; o envio externo (e-mail/API) fica para a F2,
com HITL.

## 2. Decisões de Arquitetura

**1. `COMMON_TOOLS` em `tools/common.py`, separada dos `TOOLS` de domínio**

A tool é transversal e não pertence a nenhum especialista. Embuti-la em cada
`tools/*.py` a triplicaria e criaria drift (três formatos de resposta que
teriam de mudar juntos). Embuti-la nas fábricas seria pior: as fábricas capturam
`repo`/`empresa_id` e a tool comum **não é tenant-scoped**, então a fábrica
carregaria uma dependência inútil e a tool continuaria triplicada. Cada nó
combina `[*TOOLS, *COMMON_TOOLS]` no ponto de composição, criando uma lista nova
sem mutar nenhuma das fontes; `create_specialist_node` ainda copia com
`list(tools)`, e o contrato de binding fica explícito onde é montado.

**2. Assinatura `enviar_resposta_logistica(resposta: str, fontes: str = "")`**

`resposta` é obrigatória, porque sem conteúdo não há composição; `fontes` é
opcional porque nem toda resposta terá base citável. O argumento espelha o modelo
`Recommendation` (design.md:155; `db/models.py:194`), cujo `fontes` é
`list[str] | None` — mas no caminho LLM uma **string legível** (“estoque, TMS”)
é o contrato natural para function calling. A estruturalização em `list[str]` é
responsabilidade da T21, não desta tool. O schema derivado pelo `@tool` expõe
`fontes` com `default: ""`, sem forçar o LLM a inventar fontes.

**3. Composição textual e puramente read-only, com sentinelas de módulo**

O design.md:178 classifica a F1 como “compõe a resposta ao usuário (sem envio
externo)”; o envio real é F2 com HITL (STATE.md, Deferred Ideas). As constantes
`_ROTULO` e `_FONTES_VAZIAS` evitam strings mágicas e fixam as bordas: `fontes`
vazio vira “não informadas”; `resposta` vazia curto-circuita em “Nenhum conteúdo
para compor a resposta logística.” antes de formatar, evitando um rótulo órfão.

**4. `COMMON_TOOLS` exportada por `tools/__init__.py` e consumida pelos nós**

Manter o catálogo do pacote descoberto num único `__all__` segue o padrão das
T14/T15/T16. Importar `gestlog.tools.common` diretamente nos nós evita acoplar o
nó a um eventual reagrupamento do `__all__`. Na T17 a composição passou para
dentro dos builders (`[*base, *COMMON_TOOLS]`), mas a `COMMON_TOOLS` continua
**sempre** anexada — é essa invariante que a T34 garante.

## 3. Concessões e Escolhas Práticas (Trade-offs)

- **`fontes` como `str` no schema, e não `list[str]`:** o LLM lida melhor com um
  campo textual único e a conversão para a lista persistida fica na T21.
  Perde-se validação estrutural na borda da tool, aceitável porque a F1 não
  persiste a resposta pela tool.
- **O nome “enviar” convive com comportamento read-only:** o nome vem do catálogo
  (`send_logistics_response`, AD-010) e do design; docstring e ADR deixam
  explícito que não há envio na F1. Renomear a tool quebraria o contrato
  documentado.
- **O prompt dos especialistas ainda não instrui a chamada da tool:** a T34 só
  exige que os três a exponham; orientar o LLM (ou o roteamento da T21) é
  iteração seguinte. O nó já a disponibiliza no `bind_tools` e a composição está
  coberta por teste.
- **`COMMON_TOOLS` é uma lista mutável de módulo:** nenhum consumidor a muta
  (`[*...]` e `list(tools)` copiam), então o estado global não vaza entre nós; um
  consumidor futuro que a mutasse quebraria o contrato implícito.
- **`fontes` vazio não distingue “não havia fonte” de “o LLM omitiu”:** ambos
  caem em “não informadas”; refinamento fica para a extração estruturada da T21.
- **Mock e fábrica coexistem:** o `TOOLS` mock permanece como fallback do REPL
  (`cli.py`) até a interface web/CLI receber banco, e sua remoção (pós-T17) **não
  inclui** `tools/common.py`.

## 4. O que vem a seguir (Roadmap Imediato)

- **T17 (Copilot Service):** os builders passam a receber `tools` opcional e a
  compor `[*base, *COMMON_TOOLS]` internamente, mantendo a tool comum sempre
  anexada ao binding; é também onde as fábricas por tenant entram no grafo.
- **T18/T19 (SSE e UI do chat):** expõem e consomem a resposta composta.
- **T21 (recomendação/fontes):** converte a string `fontes` no `list[str]` do
  `Recommendation` e passa a orientar o roteamento da tool.

## 5. Validação de Qualidade e Segurança

- **Garantias de negócio e privacidade:** a tool comum não é tenant-scoped e não
  entra em closure de fábrica; a composição é textual e não persiste dados, então
  não há superfície de vazamento entre empresas. `test_specialists_expoem_tool_comum`
  confirma que os três especialistas a expõem no binding.
- **Cobertura e testes automatizados:** o contrato da tool foi verificado no
  schema derivado pelo LangChain (`resposta` obrigatória, `fontes` com
  `default: ""`); a composição e os dois edges (sem fontes, resposta vazia) por
  `test_common_tool_compoe_resposta`. Sem mutação/compartilhamento:
  `[*TOOLS, *COMMON_TOOLS]` cria lista nova nos três nós e
  `create_specialist_node` copia de novo com `list(tools)`. Gate `pytest` →
  115 passed, cobertura 97.27% (`tools/common.py` 100%); `black --check` → 65
  files unchanged; `ruff check` → All checks passed.
- **Padrões de qualidade:** docstring e ADR explicitam o comportamento
  read-only, alinhando nome do catálogo e semântica real.

## Achados corrigidos no self-review

- **Identificador de teste com caractere não-ASCII:**
  `test_common_tool_compõe_resposta` usava `õ` no nome da função, destoando da
  convenção do codebase (identificadores ASCII, acentos só em
  docstrings/strings). Renomeado para `test_common_tool_compoe_resposta`.
- Sem achados de lint/formatação.
