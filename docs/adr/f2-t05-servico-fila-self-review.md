# ADR: f2-t05-servico-fila

## 1. Contexto & Objetivo

A T5 fecha a fase de domínio da fila HITL da F2: o `CorrectionService`
(`src/gestlog/correcoes/servico.py`) transforma os cadastros incompletos do tenant
em **itens acionáveis** de correção. Ela costura as três peças anteriores — as regras
de completude (T3), a sugestão determinística (T4) e o `CorrectionRepository`
escopado por empresa (T2) — e entrega duas operações: `gerar_fila()`, que materializa
um item pendente por campo faltante, e `listar(status, limite)`, que alimenta a futura
tela de fila. O ganho prático é o que a história P1 promete: o gestor abre a visão de
correções e encontra, para cada lacuna do cadastro, um item com valor sugerido,
justificativa e fonte — pronto para aprovação humana (INC-01/02/04, SUG-04, APR-01).

O desafio central não é "criar linhas", e sim **materializar de forma idempotente e
sem vazar tenants**. Três tensões governam a task: (a) **não duplicar trabalho** —
reabrir a fila não pode multiplicar pendentes, e uma rejeição não pode renascer a cada
carregamento; (b) **respeitar o histórico** — uma decisão terminal só é revisitada
quando o dado do cadastro realmente muda, o que exige comparar o snapshot guardado com
o valor atual; e (c) **fronteira AD-002** — a escrita/leitura da fila vive fora do
grafo, de modo que nenhum caminho do LLM alcance o catálogo.

## 2. Decisões Arquiteturais

**1. `gerar_fila()` é a unidade de trabalho da materialização: uma passada sobre os
três catálogos, dedup por item e um único `commit` ao final.**

O método percorre `_FONTES_CADASTRO` (estoque, fornecedores, transporte), carrega os
registros do **`empresa_id` da sessão** via `fabrica(self.session).list(self.empresa_id)`
e, para cada campo ausente (`campos_faltantes`, T3), decide se cria. Só ao terminar a
varredura há `self.session.commit()`. Isso dá sentido transacional à operação: a fila
é vista como um todo consistente, e falha no meio não deixa itens órfãos de commit. O
`commit` aqui é deliberado porque o design determina que a rota `GET /correcoes`
materializa e persiste na própria requisição; o serviço é, portanto, a fronteira da
UoW de geração. Os métodos de decisão (`aprovar`/`rejeitar`, T7/T8) terão as próprias
fronteiras e não compartilham transação com esta, o que evita commit aninhado.

**2. A idempotência é composta por duas consultas do repositório, e a *ordem* das
regras é o que a torna correta.**

A regra do design tem dois critérios independentes: (1) existe item **aberto**
(`pendente`/`aprovado`) para `(tipo, alvo_chave, campo)` → não cria, **qualquer** que
seja o valor; (2) existe item terminal com o **mesmo `valor_no_pedido`** → não cria (o
"sticky": a decisão anterior permanece até o dado mudar); (3) caso contrário → cria um
novo `pendente`. O código expressa isso na ordem exata em que as regras importam:
primeiro `repo.abertos_para(...)` (sem filtro de valor) e só então
`repo.existe_para(..., valor_no_pedido)`. Como `abertos_para` já eliminou todo item
aberto do par alvo/campo, a segunda consulta só pode encontrar **terminais** — o que
faz `existe_para` (que considera qualquer status, decisão documentada na T2) cumprir a
regra 2 sem uma terceira consulta SQL. Se a ordem fosse invertida ou se `abertos_para`
filtrasse por valor, um item aberto criado com snapshot antigo deixaria de suprimir um
novo item, reabrindo a duplicação que a idempotência existe para evitar.

**3. O pareamento `tipo → (repositório, chave de identidade)` mora no serviço, não no
domínio puro, e tem uma trava de paridade com a T3.**

O mapa `_FONTES_CADASTRO` é a única peça do épico que associa cada tipo ao seu
repositório e à coluna de identidade (`estoque → StockRepository/sku`,
`fornecedores → SupplierRepository/fornecedor_id`,
`transporte → TransportRepository/codigo_rastreio`). Ele fica no serviço — a camada
que já fala com `repositories` — porque colocá-lo em `completude.py` faria o domínio
puro (que não tem dependências de banco) importar repositórios, violando a direção
`agents → libs`. O risco dessa nova tabela indexada por `tipo` é a divergência
silenciosa com `_CAMPOS` da T3 (**L-013**): um tipo novo em completude sem entrada no
mapa nunca materializaria item algum, e uma chave digitada errada só explodiria em
`AttributeError` no meio da geração. Por isso o self-review acrescentou
`test_mapa_de_fontes_cobre_tipos_e_chaves_da_completude`, que afirma a **igualdade**
`set(_FONTES_CADASTRO) == set(_CAMPOS)` e que cada `chave` é, de fato, uma coluna
mapeada do modelo do repositório. Um tipo novo sem par (ou um `sku`/`fornecedor_id`
trocado) quebra a suíte na hora, em vez de virar uma fila incompleta em produção.

**4. `alvo_chave` é normalizada na mesma forma canônica dos catálogos
(`strip().upper()`), tornando o item recomponível com o registro.**

O `get_by_sku`/`get_by_fornecedor_id`/`get_by_codigo` e os `upsert` dos catálogos
guardam as identidades em caixa alta e sem espaços nas pontas. O serviço usa
`str(getattr(registro, chave) or "").strip().upper()` para gravar `alvo_chave`. Essa
coerência é o que permite à T7 resolver o alvo pelo item ("registro alvo") e à dedup
funcionar entre gerações sucessivas, mesmo que o cadastro tenha sido importado com
variações de caixa. O `or ""` ainda cobre a identidade nula, impedindo que
`str(None)` vire a string `"None"` — um alvo-fantasma que nunca casaria com registro
algum.

**5. O contexto da sugestão é a própria lista de irmãos do tenant, passada por
identidade, e o isolamento vem da consulta escopada.**

`_materializar` repassa a mesma `registros` (a lista carregada por `empresa_id`) a
`sugerir` (T4). Como `sugerir` exclui o alvo por identidade de objeto
(`outro is not registro`), o contrato só se sustenta se o serviço passar a **mesma
instância** — e é o que ele faz. O isolamento por tenant não depende dessa exclusão:
ele é garantido na origem, porque `repo.list(self.empresa_id)` é a única porta que
monta o contexto e nunca devolve linhas de outro cliente. Assim, a sugestão de um
item jamais é calculada sobre dados alheios (INC-03, NFR-03), o que o teste de
isolamento com dois tenants fixa.

**6. `listar` delega ao repositório e a paginação (EDG-08) entra como parâmetro, sem
reimplementar SQL no serviço.**

`listar(status="pendente", limite=None)` chama
`CorrectionRepository.list_by_status(self.empresa_id, status, limite)`. O
`list_by_status` ganhou o argumento opcional `limite` (`.limit()`), preservando a
ordenação determinística por `created_at, id`. O serviço não monta consulta: mantém a
regra de que só `libs` fala SQL, e a T10 decide o tamanho de página. Isso também
preserva o estado vazio (EDG-06/07): um tenant sem dados devolve `[]` sem erro, e a
tela distingue "sem dados importados" de "fila vazia" no seu próprio contexto.

## 3. Trade-offs e Compromissos

- **`existe_para` considera qualquer status, não só terminais.** É a decisão herdada
  da T2 e só é segura *porque* `abertos_para` roda antes. Mantida em vez de criar uma
  consulta `terminais_para` dedicada: a duplicação é inofensiva aqui e evita mais um
  método SQL para uma regra que o serviço já expressa na ordem das chamadas. Fica
  registrado que a correção depende dessa ordem — invertê-la muda a semântica.
- **`gerar_fila` carrega todos os registros dos três tipos em memória.** A definição
  de "incompleto" é derivada das colunas (vazio/zero/default), então não há predicado
  SQL que a empurre para o banco sem duplicar a tabela de completude; carregar e
  filtrar em memória é o caminho fiel ao design. O custo é O(n) por tipo por geração.
  Aceitável porque a geração é idempotente e a EDG-08 (paginação) incide sobre a
  **listagem**, não sobre a varredura. Um tenant muito grande pedirá agregação/limite
  na amostra de sugestão (limitação já anotada na ADR da T4).
- **O `commit` dentro de `gerar_fila` assume que o serviço é a fronteira da UoW.**
  Se um chamador futuro envolver a geração numa transação maior, esse `commit`
  encerraria a transação externa. Hoje os únicos consumidores previstos são a rota
  `GET /correcoes` (T10) e o próprio teste; os fluxos de decisão (T7/T8) são métodos
  separados com commits próprios, sem chamar `gerar_fila` no meio de uma transação de
  aprovação. O acoplamento está explícito para que a T7/T9 não o contornem por engano.
- **Sem *constraint* de unicidade no banco para a dedup.** A idempotência é
  aplicacional (`abertos_para`/`existe_para` + geração serializada). Duas chamadas
  concorrentes de `gerar_fila` ainda poderiam criar itens duplicados; é o *hardening*
  (índice único parcial ou `INSERT ... ON CONFLICT`) que a T2 já sinalizou e que a
  EDG-04 só exige para a **decisão**, não para a geração. Fica como evolução.
- **`limite` não é validado.** Um valor negativo cai no comportamento do dialeto
  (SQLite trata `LIMIT -1` como "sem limite"). O repositório permanece somente-SQL e a
  validação de faixa pertence à camada que monta o parâmetro (T10). Hoje não há
  chamador passando negativo.
- **A ordem de retorno de `gerar_fila` não é garantida entre bancos.**
  `EmpresaScopedRepository.list` não tem `ORDER BY`; o retorno serve para feedback
  imediato ("o que foi criado agora"), enquanto a listagem persistida — ordenada por
  `created_at, id` — é a que a UI consome. Testes usam conjuntos, não sequência.
- **Os testes de paridade alcançam símbolos privados (`_FONTES_CADASTRO`, `_CAMPOS`).**
  É a forma direta de pinçar a invariante "sem órfãos" e segue o precedente da T4; a
  alternativa (exercitar só o público) não detectaria um tipo de completude ausente do
  mapa.

## 4. Limitações Conhecidas

- **Duplicação sob concorrência.** Sem *constraint* de banco, duas gerações
  simultâneas do mesmo tenant podem materializar itens repetidos. A T7 re-lê o estado
  do item e recusa decisão duplicada (EDG-04), então o impacto é de fila, não de
  escrita; o endurecimento fica para quando o volume justificar.
- **`gerar_fila` é O(total de registros dos três catálogos) em memória.** Sem
  paginação na geração; se um tenant passar a ter dezenas de milhares de registros
  incompletos, o tempo de resposta do `GET /correcoes` cresce linearmente. A mitigação
  seria um recorte por status/limite ou agregação das sugestões.
- **O contrato de `valor_no_pedido` e de igualdade com o valor atual é verbal até a
  T7.** O `serializar` compartilhado (T3/T4) garante o formato; a prova de que a
  detecção de conflito/no-op fecha ponta a ponta chega com a T7 e a aceitação da T12.
- **A chave de identidade é um `str` no mapa, não um `Literal`/enum.** Um typo futuro
  (`"fornecedorID"`) quebra no teste de paridade, mas não no tipo; não há checagem
  estática no gate (só `ruff`).
- **`existe_para` não distingue aberto de terminal por status.** A regra 2 depende da
  precedência de `abertos_para`; documentado como trade-off.

## 5. Validação de Qualidade e Segurança

- **Garantias de negócio e isolamento:** `gerar_fila` só lê e escreve no
  `empresa_id` do serviço; `test_gerar_fila_isola_por_empresa` prova que o tenant sem
  dados gera `[]` e que a fila do tenant correto tem os 3 itens. A idempotência
  (`test_gerar_fila_e_idempotente`), o "sticky" terminal
  (`test_gerar_fila_nao_recria_item_terminal_com_mesmo_valor`), a liberação por
  mudança de valor (`test_gerar_fila_cria_novo_quando_valor_muda`), o bloqueio por item
  aberto (`test_gerar_fila_nao_duplica_item_aberto`) e a normalização de chave
  (`test_gerar_fila_normaliza_chave_em_maiuscula`) fixam as três regras de dedup do
  design. A fronteira AD-002 é estrutural: `servico.py` não importa `agents/` nem
  `graph`.
- **Achado do self-review:** adicionado
  `test_mapa_de_fontes_cobre_tipos_e_chaves_da_completude`, amarrando o mapa
  `_FONTES_CADASTRO` à fonte única de tipos (`_CAMPOS`) e às colunas reais dos modelos
  (**L-013**). O arquivo passou de 12 para 13 testes.
- **Cobertura e testes automatizados:** gate focado
  `uv run pytest tests/correcoes tests/test_repositories_correcoes.py --no-cov -q`:
  **56 passed** (era 55; +1 do self-review). Suíte completa: **336 passed, 98,50%**
  (gate de 80% ok). O `list_by_status` com `limite` é coberto por
  `test_list_by_status_respeita_limite` (EDG-08) e por
  `test_listar_filtra_status_e_limita`.
- **Padrões de qualidade:** `uv run black --check` e `uv run ruff check` verdes nos
  arquivos tocados; `from __future__ import annotations` em todos os módulos;
  docstrings em português; sem comentários fora de docstring; serviços com
  `@dataclass(frozen=True)` espelhando `CopilotService`.
- **Lição registrada:** a colisão de basename de teste que quebrou a coleta
  (`tests/correcoes/test_servico.py` × `tests/ingestion/test_servico.py`) foi
  corrigida com o rename para `test_servico_fila.py` e está gravada como **L-018**.
