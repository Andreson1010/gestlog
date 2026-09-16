# ADR: t16-transport-tools

## 1. Contexto & Objetivo

Fechando a trilha de dados por tenant iniciada na T14, o especialista de
transporte ainda respondia a partir de mocks. A T16 aplica COP-02 (persistência
das tools por tenant, design.md:261) ao domínio: `rastrear_entrega` passa a ler
do `TransportRepository` filtrado por `empresa_id` e a análise read-only
`otimizar_entrega` é acrescentada para apontar entregas que merecem atenção,
enquanto `calcular_frete` e `consultar_prazo` mantêm o cálculo determinístico. O
desafio é o mesmo das T14/T15 — trocar a fonte de dados sem mudar prompts nem
assinaturas e sem quebrar o isolamento — com uma particularidade: o modelo de
transporte da F1 não guarda tarifas nem distâncias, então parte das tools não tem
fonte persistida para ler.

## 2. Decisões de Arquitetura

**1. Fábrica `build_transport_tools(repo, empresa_id)` com o tenant no closure**

As quatro tools são construídas por chamada, capturando `repo` e `empresa_id`,
preservando o contrato do LLM (`origem`, `destino`, `peso_kg`, `codigo`) e
oferecendo o mesmo ponto único de injeção das T14/T15. O Copilot Service monta as
tools por requisição a partir do repositório e da empresa da sessão.

**2. `rastrear_entrega` e `otimizar_entrega` delegam a leitura ao repositório**

`TransportRepository.get_by_codigo` e o `list` herdado de
`EmpresaScopedRepository` já filtram `TransportRecord.empresa_id == empresa_id`
no SQL. A varredura por empresa usada por `otimizar_entrega` reaproveita `list`,
e o filtro de status é aplicado em Python porque o repositório não expõe essa
consulta — evitando duplicar a lógica de tenancy na tool.

**3. `calcular_frete`/`consultar_prazo` continuam cálculo puro, com helpers únicos**

O `TransportRecord` da F1 só tem `empresa_id`, `codigo_rastreio`, `origem`,
`destino`, `peso_kg` e `status`: **não existe tabela de tarifas nem de distâncias
por tenant**. Sem fonte persistida, o cálculo permanece a heurística
determinística (tabela de distâncias + tarifas), e `_texto_frete`/`_texto_prazo`
são os helpers compartilhados entre o mock `TOOLS` e a fábrica — fonte única, de
modo que mock e fábrica nunca divirjam. Os números mágicos foram extraídos para
constantes (`_TARIFA_POR_KM`, `_TARIFA_POR_KG`, `_KM_POR_DIA`,
`_DISTANCIA_PADRAO_KM`, `_STATUS_ATENCAO`).

**4. `otimizar_entrega` é read-only e usa matching por substring**

A análise devolve texto e decide atenção com `_exige_atencao(status)`, cujo
matching é por substring (`_STATUS_ATENCAO = ("atras", "trânsito")`). Como não há
enum de status no modelo — é um `String(120)` livre, inclusive vindo de CSV —
igualdade exata seria frágil a variações de texto; a substring reconhece
“atrasado”/“atrasada”/“em trânsito” sem exigir um enum que a F1 não tem. O helper
isola a regra e é testável.

**5. O mock determinístico permanece, sem a tool nova**

Como nas tasks anteriores, o `TOOLS` mockado segue como fallback do REPL até a
interface web/CLI receber banco. A injeção das fábricas é a **T17**, via
`specialist_tools`. A tool nova (`otimizar_entrega`) só existe no caminho por
tenant, não no mock.

## 3. Concessões e Escolhas Práticas (Trade-offs)

- **`otimizar_entrega` varre a empresa e filtra em Python** em vez de empurrar o
  status para o SQL; o repositório não tem essa consulta e criá-la seria escopo
  da camada de dados.
- **Matching sensível a acentuação:** `"atras"`/`"trânsito"` cobre o vocabulário
  das fixtures, do parser e do mock (`"em trânsito"`, `"atrasado"`), mas um CSV
  com `"em transito"` (sem acento) não é sinalizado. Normalização/enum é
  iteração futura.
- **`calcular_frete`/`consultar_prazo` são redefinidos dentro da fábrica** mesmo
  sem depender do repositório. É duplicação deliberada de wrappers finos: mantém
  a fábrica como fonte única do conjunto de tools e o mesmo formato das T14/T15,
  e cria o ponto onde uma futura tabela de tarifas por tenant será plugada. A
  lógica em si não é duplicada (helpers `_texto_*` compartilhados).
- **Análise por heurística de atenção**, não roteirização real; otimização de
  roteiro é F2.
- **Sem cache:** `otimizar_entrega` varre a empresa a cada invocação.
- **Fábrica constrói quatro objetos por chamada**, custo baixo e prematuro
  otimizar.
- **Mock e fábrica coexistem:** ponteiro corrigido para a T17 e remoção dos
  `TOOLS` mock de `inventory.py`, `suppliers.py` e `transport.py` (e seus imports
  nos nós) na migração do REPL, atualizando `tests/agents/test_specialists.py` e
  `test_inventory_tools`/`test_supplier_tools`/`test_transport_tools` de
  `tests/test_tools.py`.

## 4. O que vem a seguir (Roadmap Imediato)

- **T34 (tool comum):** fecha o conjunto de tools dos três especialistas.
- **T17 (Copilot Service):** injeta as três fábricas por tenant no grafo via
  `specialist_tools`, ligando o banco ao copiloto.
- **T18/T19 (SSE e UI do chat):** expõem e consomem a resposta do copiloto.
- **Migração do REPL:** remoção do mock de transporte quando a interface
  web/CLI receber banco, com os testes atualizados no mesmo movimento.

## 5. Validação de Qualidade e Segurança

- **Garantias de negócio e privacidade:** toda leitura é escopada por
  `empresa_id`; o teste de isolamento prova que o mesmo `GL-1` de outro tenant
  não vaza.
- **Cobertura e testes automatizados:** sem regressão no cálculo —
  `test_transport_factory_mantem_calculo` fixa o resultado da fábrica (408 km /
  R$) e o edge de mesma cidade (0 km). Gate `pytest tests/test_tools.py --no-cov`
  → 20 passed; suíte completa `pytest` → 113 passed, cobertura 97.23%
  (`transport.py` 100%).
- **Padrões de qualidade:** `black --check` e `ruff check` já passavam; nenhum
  achado de lint.

## Achados corrigidos no self-review

- **Teste de isolamento não exercitava a tool do segundo tenant:** o teste
  verificava o registro cru do outro tenant no fake (`repo.get_by_codigo`), o que
  não provava que a fábrica amarra a empresa certa no closure. Passou a construir
  as tools também para o outro tenant e afirmar que `GL-1` resolve para
  `"entregue"` nesse tenant e para `"em trânsito"` no primeiro.
- **Helpers privados sem docstring:** `_normalizar` e `_distancia_km` ganharam
  docstring em português, alinhando ao restante do módulo e às convenções do
  AGENTS.md.
