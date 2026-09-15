# ADR: t34-common-response

## 1. Context & Goal

A T34 implementa a tool comum do catálogo F1 (AD-010, design.md:178-181):
`enviar_resposta_logistica`, compartilhada pelos três especialistas (estoque,
fornecedores e transporte), com fonte única em `src/gestlog/tools/common.py`. O
desafio não é algoritmo (não há I/O): é decidir **onde** a tool comum mora e
**como** ela se combina com as tools de domínio sem duplicação e sem contaminar
o escopo por tenant que as T14/T15/T16 estabeleceram. A F1 é read-only (AD-001):
a tool apenas **compõe o texto final** — o envio externo (e-mail/API) fica para a
F2 com HITL.

## 2. Architectural Decisions

- **Decision 1:** `COMMON_TOOLS` vive em `tools/common.py`, separado dos `TOOLS`
  de domínio, e cada nó combina com `[*TOOLS, *COMMON_TOOLS]` na chamada a
  `create_specialist_node`.
  - **Justification:** A tool comum é transversal e não pertence a nenhum
    domínio. Embuti-la em cada `tools/*.py` a duplicaria em três arquivos e
    criaria drift (três formatos de resposta que precisariam mudar juntos).
    Embuti-la na fábrica (`build_*_tools`) seria pior: as fábricas capturam
    `repo`/`empresa_id` e a tool comum **não é tenant-scoped**, então a fábrica
    teria uma dependência inútil e a tool continuaria triplicada. O splat
    `[*TOOLS, *COMMON_TOOLS]` cria uma lista nova a cada nó, sem mutar nenhuma das
    fontes — `create_specialist_node` ainda faz `list(tools)` internamente, e o
    contrato de binding fica explícito no ponto de composição.
- **Decision 2:** Assinatura `enviar_resposta_logistica(resposta: str, fontes:
  str = "") -> str`, com `fontes` **opcional** (default `""`).
  - **Justification:** `resposta` é obrigatória (sem conteúdo não há composição);
    `fontes` é opcional porque nem toda resposta terá base citável, e o argumento
    espelha o modelo `Recommendation` (design.md:155; `db/models.py:194`) cujo
    `fontes` é `list[str] | None` — no caminho LLM, porém, uma **string legível**
    ("estoque, TMS") é o contrato natural para function calling; a
    estruturalização em `list[str]` é responsabilidade da T21 (extração de
    recomendação/fontes), não desta tool. O schema derivado pelo `@tool` expõe
    `fontes` com `default: ""`, sem forçar o LLM a inventar fontes.
- **Decision 3:** A composição é textual e puramente read-only, sem envio
  externo, com os sentinelas `_ROTULO` e `_FONTES_VAZIAS`.
  - **Justification:** O design.md:178 classifica a F1 como "compõe a resposta ao
    usuário (sem envio externo)"; o envio real é explicitamente F2 com HITL
    (STATE.md, Deferred Ideas). Constantes de módulo evitam strings mágicas
    espalhadas e fixam o comportamento de borda: `fontes` vazio -> "não
    informadas"; `resposta` vazia -> "Nenhum conteúdo para compor a resposta
    logística." (curto-circuito antes de formatar, evitando um rótulo órfão).
- **Decision 4:** `COMMON_TOOLS: list[BaseTool]` é exportado por `tools/__init__.py`
  e consumido diretamente pelos três construtores de nó, ao lado dos `TOOLS`
  mockados (andaime).
  - **Justification:** Mantém o catálogo de tools do pacote descoberto em um único
    `__all__` (padrão das T14/T15/T16) e preserva o caminho mock enquanto o
    Copilot Service (T17, não T19) injeta as fábricas por tenant. Na T17 a
    composição passou para dentro dos builders (`[*base, *COMMON_TOOLS]`), mas a
    `COMMON_TOOLS` continua sempre anexada. Importar `gestlog.tools.common`
    diretamente nos nós evita acoplar o nó ao reagrupamento de `__all__`.

## 3. Trade-offs & Compromises

- **`fontes` como `str` no schema, e não `list[str]`:** o LLM lida melhor com um
  campo textual único e a conversão para a lista persistida fica na T21. Perde-se
  validação estrutural na borda da tool; aceitável porque a F1 não persiste a
  resposta pela tool e a T21 é quem monta o `Recommendation`.
- **Bound em 3 nós via string "enviar" x comportamento read-only:** o nome vem do
  catálogo (`send_logistics_response`, AD-010) e do design.md; a docstring e a
  ADR deixam explícito que não há envio na F1. Renomear a tool quebraria o
  contrato documentado do catálogo.
- **Fonte única de composição, mas o prompt dos especialistas ainda não instrui o
  uso explícito da tool:** a T34 exige apenas que os três a exponham; orientar o
  LLM a chamá-la (ou o roteamento da T21) é iteração seguinte. Aceitável: o nó já
  a disponibiliza no `bind_tools` e a composição está coberta por teste.

## 4. Known Limitations

- **Sem envio externo (por design na F1):** e-mail/API e aprovação HITL são F2
  (STATE.md, Deferred Ideas). A tool é apenas compositora de texto.
- **Prompt não direciona o uso da tool:** os especialistas a têm disponível, mas
  nada no `PROMPT` a cita. Até o roteamento da T17/T21, o LLM pode optar por não
  chamá-la. Não é regressão (as tools de domínio continuam respondendo), apenas
  deixa a composição padronizada disponível.
- **`COMMON_TOOLS` é uma lista mutável de módulo:** nenhum consumidor a muta
  (`[*TOOLS, *COMMON_TOOLS]` e `list(tools)` copiam), então o estado global não
  vaza entre nós; se um consumidor futuro a mutar, quebra o contrato implícito.
- **`fontes` vazio não distingue "não havia fonte" de "o LLM omitiu":** ambos
  caem em "não informadas". Refinamento fica para a extração estruturada da T21.
- **Ponteiro corrigido (T17, não T19):** a troca do `TOOLS` mock pelas fábricas
  (`build_inventory_tools` / `build_supplier_tools` / `build_transport_tools`)
  acontece na T17. Nela, os builders passaram a receber `tools` opcional e a
  compor `[*base, *COMMON_TOOLS]` internamente, mantendo a `COMMON_TOOLS` sempre
  anexada ao binding. A tool comum **não é tenant-scoped** e não entra no
  closure/fábrica; removê-la do binding dos especialistas regride a T34. O
  `TOOLS` mock permanece como fallback do REPL (`cli.py`) até a interface
  web/CLI receber DB; sua remoção (pós-T17) não inclui `tools/common.py`.

## Achados corrigidos no self-review

- **Identificador de teste com caractere não-ASCII:** `test_common_tool_compõe_resposta`
  usava `õ` no nome da função, destoando da convenção do codebase (identificadores
  ASCII, acentos só em docstrings/strings). Renomeado para
  `test_common_tool_compoe_resposta`.
- Sem achados de lint/formatação: `black --check` e `ruff check` já passavam.
- Contrato da tool verificado no schema derivado pelo LangChain: `resposta`
  obrigatória, `fontes` com `default: ""` (opcional de fato).
- Sem mutação/compartilhamento: `[*TOOLS, *COMMON_TOOLS]` cria lista nova nos três
  nós e `create_specialist_node` copia de novo com `list(tools)`.
- Consistência de binding confirmada nos três especialistas por
  `test_specialists_expoem_tool_comum`; a composição e os dois edges (sem fontes,
  resposta vazia) por `test_common_tool_compoe_resposta`.
- Gate final: `pytest` -> 115 passed, cobertura 97.27% (`tools/common.py` 100%);
  `black --check` -> 65 files unchanged; `ruff check` -> All checks passed.
