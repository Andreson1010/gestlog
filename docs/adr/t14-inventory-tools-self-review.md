# ADR: t14-inventory-tools

## 1. Contexto & Objetivo

O especialista de estoque respondia com dados mockados e determinísticos: úteis
para desenvolver o grafo, inúteis para o operador, porque não refletiam o estoque
da empresa dele. A T14 aplica o requisito COP-02 (persistência das tools por
tenant, design.md:261) ao domínio de estoque: as tools de leitura
(`consultar_estoque`, `calcular_reposicao`, `listar_movimentacoes`) passam a ler
do `StockRepository` filtrado por `empresa_id`, e três análises read-only
(`prever_demanda`, `otimizar_armazem`, `otimizar_custos`) são acrescentadas. O
desafio não é criar consultas, e sim **trocar a fonte de dados sem mudar o
contrato que o LLM enxerga** — os mesmos nomes de tool e os mesmos argumentos —
garantindo ao mesmo tempo que cada empresa só veja os próprios dados, com o
`empresa_id` vindo do contexto da sessão e nunca de um argumento manipulável.

## 2. Decisões de Arquitetura

**1. Fábrica `build_inventory_tools(repo, empresa_id)` que prende o tenant em um closure**

As seis tools são construídas por chamada, capturando `repo` e `empresa_id` no
closure em vez de receberem a empresa como argumento. Isso preserva exatamente a
assinatura esperada pelo LLM — que continua chamando `consultar_estoque(sku)` sem
saber de tenancy — e cria um ponto único de injeção: o Copilot Service monta as
tools por requisição a partir do repositório e da empresa da sessão autenticada.
A alternativa, adicionar `empresa_id` às assinaturas, exporia a fronteira de
isolamento ao modelo e ao operador.

**2. Reutilizar as operações escopadas do repositório, sem SQL novo**

`StockRepository.get_by_sku` e o `list` herdado de `EmpresaScopedRepository` já
filtram `StockItem.empresa_id == empresa_id` na camada de banco. As tools apenas
delegam; não há duplicação da lógica de tenancy nem risco de um filtro ser
esquecido numa consulta nova. O isolamento entre clientes do SaaS fica garantido
onde ele é mais forte — no SQL — e não apenas na apresentação.

**3. As três análises são read-only e devolvem texto**

`prever_demanda`, `otimizar_armazem` e `otimizar_custos` derivam indicações a
partir dos dados existentes sem persistir nada. O catálogo (design.md) as
classifica como análise F1 (leitura/derivação); como não há mutação, não há HITL
nem risco de escrita indevida, e manter o mesmo contrato textual das tools de
leitura simplifica tanto o especialista quanto o REPL.

**4. O período de cobertura vive numa constante única**

`_DIAS_COBERTURA = 30` centraliza o horizonte usado tanto por `calcular_reposicao`
quanto por `prever_demanda`, evitando que os dois números divirjam com o tempo.

**5. O mock determinístico permanece, como andaime do REPL**

O `TOOLS` mockado não foi removido: o REPL ainda não tem acesso a um repositório
concreto. A injeção das fábricas por tenant acontece na **T17** (Copilot Service),
não na T19 — o grafo recebe as tools via `specialist_tools`. O mock segue como
fallback do `cli.py` até a interface web/CLI ganhar banco, e o novo caminho é
exercitado pelos testes de fábrica.

## 3. Concessões e Escolhas Práticas (Trade-offs)

- **`listar_movimentacoes` devolve texto fixo** (“sem movimentações
  registradas”), porque o `StockItem` não modela movimentações — o mock tinha
  uma estrutura `_MOVIMENTACOES` que não existe no modelo de dados. A assinatura
  (`sku -> str`) e a semântica read-only são preservadas; movimentações reais
  ficam para uma tabela futura, sem quebrar o contrato da tool.
- **Análises por heurística simples** (`quantidade < minimo`,
  `quantidade > minimo * 2`) em vez de um motor de otimização real. Satisfaz o
  critério de “dado insuficiente para recomendar / orientação do que importar” no
  MVP.
- **Sem camada de cache:** as análises chamam `list` (varredura por empresa) a
  cada invocação. Aceitável no volume atual; um cache por empresa é candidato se
  o catálogo crescer.
- **Fábrica constrói seis objetos por chamada.** O custo de construção é baixo e
  a reconstrução por requisição é justamente o que garante a tenancy correta.
- **Mock e fábrica coexistem:** há risco de as tools mockadas continuarem em uso
  por engano. Mitigação: corrigir o ponteiro para a T17 e, na migração do REPL,
  remover o `TOOLS` mock de `inventory.py` e `agents/inventory.py`, atualizando
  `tests/agents/test_specialists.py` e `tests/test_tools.py::test_inventory_tools`.

## 4. O que vem a seguir (Roadmap Imediato)

- **T15/T16 (fornecedores e transporte):** o mesmo padrão de fábrica por tenant é
  replicado para os outros dois especialistas.
- **T34 (tool comum):** `enviar_resposta_logistica` é anexada aos três domínios.
- **T17 (Copilot Service):** injeta `build_inventory_tools` no grafo via
  `specialist_tools`, fechando o caminho do banco ao copiloto.
- **Migração do REPL:** remoção do `TOOLS` mock quando a interface web/CLI receber
  banco, com os testes atualizados no mesmo movimento.

## 5. Validação de Qualidade e Segurança

- **Garantias de negócio e privacidade:** cada tool usa operações escopadas por
  `empresa_id`; o teste de isolamento prova que a mesma `SKU-1` de outra empresa
  não vaza para o tenant consultado.
- **Cobertura e testes automatizados:** cada tool tem caso feliz e borda (SKU
  ausente, `consumo_medio_dia <= 0`, tenant vazio); gate
  `pytest tests/test_tools.py --no-cov` → 10 passed.
- **Padrões de qualidade:** `black --check` e `ruff check` já passavam nos
  arquivos revisados; nenhum achado de estilo no self-review.

## Achados corrigidos no self-review

- Nenhum achado de estilo ou lint.
- Cobertura e isolamento confirmados por teste, incluindo o caso de borda de
  consumo médio não positivo e o teste de isolamento entre empresas.
