# ADR: t15-supplier-tools

## 1. Contexto & Objetivo

Pelo mesmo motivo do estoque (T14), o especialista de fornecedores precisava
deixar de responder com dados fictícios e passar a enxergar os fornecedores
reais da empresa. A T15 aplica COP-02 (persistência das tools por tenant,
design.md:261) ao domínio de fornecedores: as tools de leitura
(`listar_fornecedores`, `consultar_fornecedor`, `avaliar_desempenho`) passam a
ler do `SupplierRepository` filtrado por `empresa_id`, e a análise read-only
`tratar_conformidade` é acrescentada para sinalizar fornecedores problemáticos
sem alterar nada. O desafio é o mesmo das T14/T15: trocar a fonte de dados sem
mudar prompts nem assinaturas, e manter o isolamento com o `empresa_id` vindo da
sessão, não de um argumento da tool.

## 2. Decisões de Arquitetura

**1. Fábrica `build_supplier_tools(repo, empresa_id)` com o tenant no closure**

As quatro tools são construídas por chamada, capturando `repo` e `empresa_id`.
O LLM continua vendo o contrato original (`categoria`, `fornecedor_id`) sem
saber de tenancy, e o Copilot Service ganha um ponto único de injeção por
requisição, montando as tools a partir do repositório e da empresa da sessão.
É deliberadamente o mesmo padrão da T14, para que o codebase tenha uma única
forma de ligar dados de tenant às tools.

**2. Leitura delegada às operações já escopadas do repositório**

`SupplierRepository.get_by_fornecedor_id` e o `list` herdado de
`EmpresaScopedRepository` filtram `Supplier.empresa_id == empresa_id` no SQL.
As tools só delegam: a lógica de tenancy vive na camada de banco, não
reimplementada em cada tool.

**3. `tratar_conformidade` read-only, com limiares nomeados e helper de motivos**

A checagem devolve texto e usa constantes de módulo (`_AVALIACAO_MINIMA = 4.0`,
`_PRAZO_MAXIMO_DIAS = 15`) mais o helper `_motivos_conformidade(fornecedor)`. O
catálogo classifica a checagem como análise F1 (leitura/derivação), então não há
HITL nem mutação, e o contrato textual é o mesmo das demais tools. As constantes
eliminam “números mágicos” e o helper isola a regra, que fica testável por
limite (4.0 e 15 dias são conformes).

**4. O mock determinístico permanece como andaime do REPL**

Assim como na T14, o `TOOLS` mockado não sai nesta task: o REPL ainda não tem
repositório concreto. A injeção das fábricas ocorre na **T17**, via
`specialist_tools` no grafo, e o mock permanece como fallback até a interface
web/CLI receber banco.

## 3. Concessões e Escolhas Práticas (Trade-offs)

- **`avaliar_desempenho` resume o cadastro** (nota, prazo, status) em vez de
  devolver o histórico textual de ocorrências do mock (`_OCORRENCIAS`), que o
  modelo `Supplier` não armazena. Assinatura (`fornecedor_id -> str`) e
  semântica read-only preservadas; histórico real fica para uma tabela futura.
- **`listar_fornecedores`/`tratar_conformidade` varrem a empresa e filtram em
  Python**, pois o repositório não expõe consulta por categoria e criar uma
  seria escopo da camada de dados. Aceitável no volume do MVP.
- **Limiares fixos de conformidade** (4.0 / 15 dias) em vez de configuráveis por
  política do cliente; parametrização é F2.
- **Fábrica constrói quatro objetos por chamada**, custo baixo e prematuro
  otimizar; a reconstrução por requisição garante a tenancy.
- **Mock e fábrica coexistem**, com o mesmo risco e a mesma mitigação da T14:
  ponteiro corrigido para a T17 e remoção do mock na migração do REPL,
  atualizando `tests/agents/test_specialists.py` e
  `tests/test_tools.py::test_supplier_tools`.

## 4. O que vem a seguir (Roadmap Imediato)

- **T16 (transporte):** replica o padrão de fábrica por tenant no terceiro
  especialista.
- **T34 (tool comum):** `enviar_resposta_logistica` é anexada aos três
  especialistas.
- **T17 (Copilot Service):** injeta `build_supplier_tools` no grafo via
  `specialist_tools`.
- **Migração do REPL:** remoção do `TOOLS` mock quando a interface web/CLI
  receber banco.

## 5. Validação de Qualidade e Segurança

- **Garantias de negócio e privacidade:** toda tool usa operações escopadas por
  `empresa_id`; o teste de isolamento prova que a mesma `F-1` de outro tenant não
  vaza.
- **Cobertura e testes automatizados:** `test_supplier_factory_conformidade_limites`
  fixa a semântica inclusiva (4.0/15 conformes; 3.9/16 não conformes). Gate
  `pytest tests/test_tools.py --no-cov` → 16 passed; suíte completa `pytest` →
  108 passed, cobertura 97% (`suppliers.py` 100%).
- **Padrões de qualidade:** `black --check` e `ruff check` já passavam; nenhum
  achado de lint.

## Achados corrigidos no self-review

- **Limites de conformidade sem teste:** a comparação é estrita (`avaliacao <
  4.0`, `prazo_dias > 15`), ou seja, 4.0 e 15 dias são conformes — mas isso não
  estava fixado. Adicionado `test_supplier_factory_conformidade_limites` cobrindo
  4.0/15 (conforme) e 3.9/16 (não conforme), ancorando a semântica inclusiva.
- Sem achados de lint/formatação; sem vazamento de tenant (teste de isolamento).

## Nota de manutenção

- **`build_supplier_tools` tem ~67 linhas**, acima do guia de 50 linhas do
  AGENTS.md, por serem tools aninhadas que precisam do closure; o mesmo padrão
  existe em `build_inventory_tools` (T14, ~96 linhas). Extrair para funções de
  módulo exigiria passar `repo`/`empresa_id` explicitamente e seria um refactor
  compartilhado entre `inventory.py` e `suppliers.py`, adiado para não divergir
  do baseline da T14.
