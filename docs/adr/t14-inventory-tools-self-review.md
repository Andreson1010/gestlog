# ADR: t14-inventory-tools

## 1. Context & Goal

A T14 aplica o requisito COP-02 ("persistência de dados das tools por tenant",
design.md:261) ao especialista de estoque. As tools de leitura
(`consultar_estoque`/`calcular_reposicao`/`listar_movimentacoes`) passaram a ler
do `StockRepository` filtrado por `empresa_id`, e foram adicionadas três tools
read-only de análise (`prever_demanda`, `otimizar_armazem`, `otimizar_custos`).
O desafio técnico é trocar a fonte de dados (mock determinístico -> repositório
do tenant) **sem mudar prompts nem assinaturas** chamadas pelo LLM, e garantir o
isolamento entre clientes do SaaS (o `empresa_id` vem do contexto da sessão, não
de argumento de tool).

## 2. Architectural Decisions

- **Decision 1:** `build_inventory_tools(repo: StockRepository, empresa_id: UUID)`
  como fábrica que constrói as 6 tools por closure, capturando `repo` e
  `empresa_id`.
  - **Justification:** Prende a empresa no closure em vez de adicionar
    `empresa_id` às assinaturas das tools, preservando exatamente o contrato
    esperado pelo LLM (mesmos nomes/argumentos). Também dá um ponto único de
    injeção: o Copilot Service constrói as tools por requisição a partir do repo
    e da empresa da sessão autenticada.
- **Decision 2:** Reutilizar as operações do repositório existentes
  (`get_by_sku` e `list` do `EmpresaScopedRepository`) em vez de criar consultas
  ou filtros novos.
  - **Justification:** `StockRepository.get_by_sku` e `list` já escopam por
    `empresa_id` no SQL (where `StockItem.empresa_id == empresa_id`). As tools
    só delegam, evitando duplicação de lógica de tenancy e garantindo que o
    isolamento seja aplicado na camada de banco e não só na apresentação.
- **Decision 3:** As 3 tools de análise (`prever_demanda`, `otimizar_armazem`,
  `otimizar_custos`) são read-only e devolvem texto (como as de leitura), em vez
  de devolver modelos estruturados.
  - **Justification:** O catálogo (design.md) as classifica como F1 análise
  (leitura/derivação). Como não persistem nada, não há HITL nem mutação; manter o
  mesmo contrato textual das tools de leitura simplifica o especialista e o REPL.
- **Decision 4:** O mock determinístico `TOOLS` foi mantido como andaime do grafo
  e do REPL.
  - **Justification:** O REPL ainda não tem acesso a um repositório concreto; a
    fábrica é injetada pelo Copilot Service na T17 (não na T19). O mock permanece
    como fallback do REPL (`cli.py`) até a interface web/CLI receber DB,
    preservando o funcionamento atual enquanto o novo caminho é exercitado pelos
    testes de fábrica.
- **Decision 5:** `_DIAS_COBERTURA = 30` como constante única em vez do `30`
  espalhado.
  - **Justification:** `calcular_reposicao` e `prever_demanda` compartilham o
    mesmo período de cobertura; a constante evita drift entre as duas ferramentas.

## 3. Trade-offs & Compromises

- **`listar_movimentacoes` do repositório devolve texto fixo** ("sem
  movimentações registradas") porque o `StockItem` não modela movimentações —
  o mock tinha uma estrutura `_MOVIMENTACOES` que não existe no modelo de dados.
  Isso é aceitável: a assinatura (`sku -> str`) e a semântica read-only são
  preservadas; o registro real de movimentações fica para iteração futura (ex.:
  tabela de movimentos) sem quebrar o contrato da tool.
- **Análise baseada em heurísticas simples** (`quantidade < minimo`,
  `quantidade > minimo * 2`) em vez de um motor de otimização real. Para o MVP
  satisfaz o critério de "dado insuficiente para recomendar / orientação do que
  importar" e os casos read-only do catálogo.
- **Fábrica constrói ferramentas por chamada** (6 objects por requisição). Custo
  de construção baixo e desnecessário otimizar prematuramente; a injeção por
  requisição é o que garante a tenancy correta.

## 4. Known Limitations

- **Movimentações não são persistidas no repositório** (ver Trade-offs): a tool
  do tenant não lista movimentos reais.
- **Sem camada de cache:** `otimizar_armazem`/`otimizar_custos` chamam `list`
  (full scan por empresa) a cada invocação. Aceitável no volume do MVP; um cache
  por empresa seria revisitado se o catálogo crescer.
- **Análises são heurísticas de regra simples**, não previsão estatística de
  demanda ou otimização de layout/roteiro — capacidade estendida fica para F2.
- **`TOOLS` mock e fábrica coexistem:** risco de as tools mockadas continuarem
  sendo usadas por engano. **Correção de ponteiro:** o ponto de injeção é a T17
  (Copilot Service), não a T19 — a T17 injeta `build_inventory_tools` pelo
  parâmetro `specialist_tools` de `build_graph`. O `TOOLS` mock permanece como
  fallback do REPL (`cli.py`) até a interface web/CLI receber DB. **Ação pendente
  (pós-T17):** remover o `TOOLS` mock de `inventory.py` + `agents/inventory.py`
  ao migrar o REPL, atualizando `tests/agents/test_specialists.py` e
  `tests/test_tools.py::test_inventory_tools`.

## Achados corrigidos no self-review

- Nenhum achado de estilo/lint: `black --check` e `ruff check` já passavam nos
  arquivos revisados.
- Cobertura e isolamento confirmados por teste: cada tool tem caso feliz + edge
  (SKU ausente, `consumo_medio_dia <= 0`, tenant vazio), e o teste de isolamento
  prova que a mesma `SKU-1` em outro tenant não vaza.
- Gate final: `pytest tests/test_tools.py --no-cov` -> 10 passed.
