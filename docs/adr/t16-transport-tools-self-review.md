# ADR: t16-transport-tools

## 1. Context & Goal

A T16 aplica o requisito COP-02 ("persistência de dados das tools por tenant",
design.md:261) ao especialista de transporte. `rastrear_entrega` passou a ler do
`TransportRepository` filtrado por `empresa_id`, e foi adicionada a tool
read-only `otimizar_entrega` (aponta entregas atrasadas/em trânsito na F1, sem
mutação). `calcular_frete`/`consultar_prazo` mantêm o cálculo determinístico.
O desafio técnico, igual ao das T14/T15, é trocar a fonte de dados (mock
determinístico -> repositório do tenant) **sem mudar prompts nem assinaturas**
chamadas pelo LLM, e garantir o isolamento entre clientes do SaaS (o
`empresa_id` vem do contexto da sessão, não de argumento de tool). O padrão é o
mesmo estabelecido em T14 (`docs/adr/t14-inventory-tools-self-review.md`) e T15
(`docs/adr/t15-supplier-tools-self-review.md`).

## 2. Architectural Decisions

- **Decision 1:** `build_transport_tools(repo: TransportRepository, empresa_id:
  UUID)` como fábrica que constrói as 4 tools por closure, capturando `repo` e
  `empresa_id`.
  - **Justification:** Prende a empresa no closure em vez de adicionar
    `empresa_id` às assinaturas das tools, preservando exatamente o contrato
    esperado pelo LLM (`origem`, `destino`, `peso_kg`, `codigo`). Dá um ponto
    único de injeção: o Copilot Service constrói as tools por requisição a partir
    do repositório e da empresa da sessão autenticada. Mesma decisão das T14/T15,
    mantendo o padrão do codebase.
- **Decision 2:** `rastrear_entrega` e `otimizar_entrega` delegam a leitura ao
  repositório (`get_by_codigo` e `list` do `EmpresaScopedRepository`) em vez de
  criar consultas ou filtros novos.
  - **Justification:** `TransportRepository.get_by_codigo` e `list` já escopam
    por `empresa_id` no SQL (`where TransportRecord.empresa_id == empresa_id`).
    As tools só delegam, evitando duplicação da lógica de tenancy e garantindo
    que o isolamento seja aplicado na camada de banco e não apenas na
    apresentação. `otimizar_entrega` precisa de varredura da empresa para
    agregar; `list` é a operação existente, sem filtro por status no SQL.
- **Decision 3:** `calcular_frete`/`consultar_prazo` continuam **cálculo puro**,
  sem tocar o repositório, reaproveitando os helpers de módulo
  `_texto_frete`/`_texto_prazo` (também usados pelo mock `TOOLS`).
  - **Justification:** O modelo de dados da F1 (`TransportRecord`) só tem
    `empresa_id`, `codigo_rastreio`, `origem`, `destino`, `peso_kg` e `status` —
    **não existe tabela de tarifas nem de distâncias por tenant**. Sem fonte
    persistida, o cálculo permanece a heurística determinística (tabela de
    distâncias + tarifas) e é fonte única via helpers, para que mock e fábrica
    nunca divirjam. Os números mágicos foram extraídos para constantes
    (`_TARIFA_POR_KM`, `_TARIFA_POR_KG`, `_KM_POR_DIA`, `_DISTANCIA_PADRAO_KM`,
    `_STATUS_ATENCAO`).
- **Decision 4:** `otimizar_entrega` é read-only e devolve texto, usando o helper
  `_exige_atencao(status)` com matching por substring
  (`_STATUS_ATENCAO = ("atras", "trânsito")`).
  - **Justification:** O catálogo (design.md) classifica a análise como F1
    (leitura/derivação); como não persiste nada, não há HITL nem mutação, e o
    contrato textual simplifica o especialista e o REPL. Não há enum de status no
    modelo (é `String(120)` livre, inclusive via importação CSV), então
    correspondência exata por igualdade seria frágil a variações de texto; a
    substring reconhece "atrasado"/"atrasada"/"em trânsito" sem exigir um enum
    que a F1 não tem. O helper isola a regra e é testável.
- **Decision 5:** O mock determinístico `TOOLS` foi mantido como andaime do grafo
  e do REPL.
  - **Justification:** O grafo e o REPL ainda não têm acesso a um repositório
    concreto; a fábrica será injetada pelo Copilot Service na T19. Manter o mock
    preserva o funcionamento atual do sistema enquanto o novo caminho é
    exercitado pelos testes de fábrica. Mesma decisão das T14/T15. Assim como nas
    predecessors, a tool nova (`otimizar_entrega`) não entra no `TOOLS` mock —
    ela só existe no caminho por tenant.

## 3. Trade-offs & Compromises

- **`otimizar_entrega` chama `list(empresa)` (full scan por empresa) e filtra em
  Python** em vez de empurrar o filtro de status para o SQL. Aceitável no volume
  do MVP; o repositório não expõe consulta por status e criar uma seria escopo da
  camada de dados.
- **Matching por substring de status** (`"atras"`/`"trânsito"`) depende da
  grafia/acentuação do valor persistido. Optou-se por não normalizar acentos nem
  introduzir enum na F1; a semântica cobre o vocabulário usado pelas fixtures,
  parser de importação e mock (`"em trânsito"`, `"atrasado"`). Caso o CSV do
  cliente use `"em transito"` (sem acento), a linha não é sinalizada — ver
  Known Limitations.
- **`calcular_frete`/`consultar_prazo` são redefinidos dentro da fábrica** mesmo
  sem depender do repositório. É duplicação de wrappers finos, deliberada: mantém
  a fábrica como fonte única do conjunto de tools do especialista e o mesmo shape
  das fábricas T14/T15, e cria o ponto onde a futura tabela de tarifas por tenant
  será plugada sem alterar código fora do closure. A lógica em si não é
  duplicada (helpers `_texto_*` compartilhados).
- **Análise por heurística simples** (atenção se status contém atraso/trânsito)
  em vez de um motor de otimização de rotas real. Satisfaz o caso read-only do
  catálogo para o MVP; otimização de roteiro fica para F2.
- **Fábrica constrói ferramentas por chamada** (4 objects por requisição). Custo
  de construção baixo e desnecessário otimizar prematuramente; a injeção por
  requisição é o que garante a tenancy correta.

## 4. Known Limitations

- **Status sem enum / matching sensível a acento:** o `TransportRecord.status` é
  texto livre; `_exige_atencao` reconhece variações que contenham `"atras"` ou
  `"trânsito"` (com acento). Valores como `"em transito"` (sem acento) ou
  sinônimos (`"extraviado"`, `"parado"`) não são sinalizados. Endereçar com enum
  de status ou normalização Unicode é iteração futura.
- **Otimização de entrega é heurística de atenção, não roteirização.** Satisfaz
  a F1; capacidade real de otimização fica para F2.
- **Sem camada de cache:** `otimizar_entrega` varre a empresa a cada invocação.
  Aceitável no volume do MVP.
- **`TOOLS` mock e fábrica coexistem:** risco de as tools mockadas continuarem
  sendo usadas por engano após a T19. **Ação concreta (T19):** no Copilot Service,
  injetar as três fábricas (`build_inventory_tools`, `build_supplier_tools` e
  `build_transport_tools(repo, empresa_id)`) e **remover os `TOOLS` mock** de
  `inventory.py`, `suppliers.py` e `transport.py` + os imports em
  `agents/inventory.py`, `agents/suppliers.py` e `agents/transport.py`,
  atualizando `tests/agents/test_specialists.py` e os testes
  `test_inventory_tools`/`test_supplier_tools`/`test_transport_tools` de
  `tests/test_tools.py`.

## Achados corrigidos no self-review

- **Teste de isolamento não exercitava a tool do segundo tenant:** o teste
  verificava o registro cru do outro tenant no fake (`repo.get_by_codigo`), o que
  não provava que a fábrica amarra a empresa certa no closure. Passou a construir
  as tools também para `outra` e afirmar que `GL-1` resolve para `"entregue"`
  nesse tenant e para `"em trânsito"` no primeiro.
- **Helpers privados sem docstring:** `_normalizar` e `_distancia_km` ganharam
  docstring em português, alinhando ao restante do módulo e às convenções do
  AGENTS.md.
- Sem achados de lint/formatação: `black --check` e `ruff check` já passavam.
- Sem vazamento de tenant: cada tool usa operações escopadas por `empresa_id`; o
  teste de isolamento prova que o mesmo `GL-1` de outro tenant não vaza.
- Sem regressão no cálculo: `test_transport_factory_mantem_calculo` fixa o
  resultado da fábrica (408 km / R$) e o edge de mesma cidade (0 km) no teste
  module-level.
- Gate final: `pytest tests/test_tools.py --no-cov` -> 20 passed; suíte completa
  `pytest` -> 113 passed, cobertura 97.23% (transport.py 100%).
