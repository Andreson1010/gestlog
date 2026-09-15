# ADR: t15-supplier-tools

## 1. Context & Goal

A T15 aplica o requisito COP-02 ("persistência de dados das tools por tenant",
design.md:261) ao especialista de fornecedores. As tools de leitura
(`listar_fornecedores`/`consultar_fornecedor`/`avaliar_desempenho`) passaram a ler
do `SupplierRepository` filtrado por `empresa_id`, e foi adicionada a tool
read-only `tratar_conformidade` (checagem de conformidade na F1, sem mutação).
O desafio técnico é trocar a fonte de dados (mock determinístico -> repositório do
tenant) **sem mudar prompts nem assinaturas** chamadas pelo LLM, e garantir o
isolamento entre clientes do SaaS (o `empresa_id` vem do contexto da sessão, não
de argumento de tool). O padrão é o mesmo estabelecido na T14
(`docs/adr/t14-inventory-tools-self-review.md`).

## 2. Architectural Decisions

- **Decision 1:** `build_supplier_tools(repo: SupplierRepository, empresa_id: UUID)`
  como fábrica que constrói as 4 tools por closure, capturando `repo` e
  `empresa_id`.
  - **Justification:** Prende a empresa no closure em vez de adicionar
    `empresa_id` às assinaturas das tools, preservando exatamente o contrato
    esperado pelo LLM (`categoria`, `fornecedor_id`). Dá um ponto único de injeção:
    o Copilot Service constrói as tools por requisição a partir do repositório e da
    empresa da sessão autenticada. Mesma decisão da T14, mantendo o padrão do
    codebase.
- **Decision 2:** Reutilizar as operações do repositório existentes
  (`get_by_fornecedor_id` e `list` do `EmpresaScopedRepository`) em vez de criar
  consultas ou filtros novos.
  - **Justification:** `SupplierRepository.get_by_fornecedor_id` e `list` já
    escopam por `empresa_id` no SQL (`where Supplier.empresa_id == empresa_id`).
    As tools só delegam, evitando duplicação de lógica de tenancy e garantindo que
    o isolamento seja aplicado na camada de banco e não apenas na apresentação.
- **Decision 3:** `tratar_conformidade` é read-only e devolve texto, com os
  limiares de conformidade nomeados em constantes de módulo
  (`_AVALIACAO_MINIMA = 4.0`, `_PRAZO_MAXIMO_DIAS = 15`) e um helper
  `_motivos_conformidade(fornecedor)`.
  - **Justification:** O catálogo (design.md) classifica a checagem como F1
    análise (leitura/derivação). Como não persiste nada, não há HITL nem mutação;
    manter o contrato textual das tools de leitura simplifica o especialista e o
    REPL. As constantes evitam "números mágicos" espalhados e o helper isola a
    regra de negócio, testável por limite (4.0/15 inclusivos).
- **Decision 4:** O mock determinístico `TOOLS` foi mantido como andaime do grafo
  e do REPL.
  - **Justification:** O grafo e o REPL ainda não têm acesso a um repositório
    concreto; a fábrica será injetada pelo Copilot Service na T19. Manter o mock
    preserva o funcionamento atual do sistema enquanto o novo caminho é exercitado
    pelos testes de fábrica. Mesma decisão da T14.

## 3. Trade-offs & Compromises

- **`avaliar_desempenho` do repositório devolve resumo cadastral** (nota, prazo,
  status) e não o histórico textual de ocorrências (`_OCORRENCIAS: "7 atrasos em
  30 pedidos..."`) que o mock tinha. O `Supplier` não modela ocorrências/atrasos.
  Aceitável: a assinatura (`fornecedor_id -> str`) e a semântica read-only são
  preservadas; histórico real de atrasos fica para iteração futura (ex.: tabela de
  ocorrências) sem quebrar o contrato da tool.
- **`listar_fornecedores`/`tratar_conformidade` chamam `list(empresa)` (full scan
  por empresa) e filtram em Python** em vez de empurrar o filtro para o SQL.
  Aceitável no volume do MVP; o repositório não expõe consulta por categoria e
  criar uma seria escopo da camada de dados.
- **Limiares de conformidade fixos no código** (4.0 / 15 dias) em vez de
  configuráveis por tenant. Satisfaz "checagem read-only na F1"; parametrização
  por política do cliente fica para F2.
- **Fábrica constrói ferramentas por chamada** (4 objects por requisição). Custo
  de construção baixo e desnecessário otimizar prematuramente; a injeção por
  requisição é o que garante a tenancy correta.

## 4. Known Limitations

- **Histórico de atrasos/ocorrências não é persistido** (ver Trade-offs): a tool do
  tenant resume apenas o cadastro.
- **Sem camada de cache:** `tratar_conformidade` varre a empresa a cada invocação.
  Aceitável no volume do MVP.
- **`build_supplier_tools` tem ~67 linhas**, acima do guia de 50 linhas do
  AGENTS.md. O motivo é serem tools aninhadas que precisam do closure; o mesmo
  padrão existe em `build_inventory_tools` (T14, ~96 linhas). Extrair para
  funções de módulo exigiria passar `repo`/`empresa_id` explicitamente e seria um
  refactor compartilhado entre `inventory.py` e `suppliers.py` — adiado para não
  divergir do baseline da T14.
- **`TOOLS` mock e fábrica coexistem:** risco de as tools mockadas continuarem
  sendo usadas por engano após a T19. **Ação concreta (T19):** no Copilot Service,
  injetar `build_supplier_tools(repo, empresa_id)` e remover o `TOOLS` mock de
  `suppliers.py` + `agents/suppliers.py`, atualizando
  `tests/agents/test_specialists.py` e `tests/test_tools.py::test_supplier_tools`.
  O mesmo vale para `build_inventory_tools` (T14) e `build_transport_tools` (T16).

## Achados corrigidos no self-review

- **Limites de conformidade sem teste:** os limiares usam comparação estrita
  (`avaliacao < 4.0`, `prazo_dias > 15`), ou seja, 4.0 e 15 dias são conformes,
  mas esse comportamento não estava fixado. Adicionado
  `test_supplier_factory_conformidade_limites` cobrindo 4.0/15 (conforme) e
  3.9/16 (não conforme), ancorando a semântica inclusiva.
- Sem achados de lint/formatação: `black --check` e `ruff check` já passavam.
- Sem vazamento de tenant: cada tool usa operações escopadas por `empresa_id`; o
  teste de isolamento prova que a mesma `F-1` de outro tenant não vaza.
- Gate final: `pytest tests/test_tools.py --no-cov` -> 16 passed; suíte completa
  `pytest` -> 108 passed, cobertura 97% (suppliers.py 100%).
