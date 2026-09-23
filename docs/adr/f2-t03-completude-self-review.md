# ADR: f2-t03-completude

## 1. Contexto & Objetivo

A T3 entrega a primeira peça do domínio de correções da F2: as **regras de completude
cadastral por tipo** em `src/gestlog/correcoes/completude.py`, reexportadas por
`src/gestlog/correcoes/__init__.py`, com os testes unitários em
`tests/correcoes/test_completude.py`.

O produto por trás da tarefa é direto: gestores importam planilhas com cadastros
incompletos e precisam que o sistema aponte **o que está faltando**, campo a campo,
antes de oferecer uma sugestão e exigir uma aprovação humana. Se essa classificação
errar para mais, o operador recebe alertas falsos e perde a confiança na fila; se
errar para menos, um cadastro furado passa despercebido. O desafio arquitetural não
está em "checar se um campo está vazio", e sim em **definir ausência de forma
explícita por tipo** — porque um `0` em `quantidade` é um valor legítimo, um
`False` em `ativo` é um estado válido, e um `SKU` é identidade, não dado a corrigir.

A tarefa também é a fundação de duas decisões do épico: a definição de "incompleto"
que governa a listagem (INC-01/INC-02) e a **serialização canônica do valor atual**,
que é o que permite detectar conflito de reimportação na aprovação (EDG-02). Por
isso as duas funções públicas — `campos_faltantes(tipo, registro) -> list[str]` e
`valor_atual(tipo, registro, campo) -> str` — precisam ser determinísticas e
rastreáveis.

## 2. Decisões Arquiteturais

**1. Uma tabela allow-list por tipo é a única fonte de verdade, e não um espelho dos
defaults do banco.**

`_CAMPOS: dict[str, dict[str, str]]` mapeia cada tipo (`estoque`, `fornecedores`,
`transporte`) para os campos verificados e sua *natureza* (`texto`, `inteiro`,
`decimal`). Tanto `campos_faltantes` quanto `valor_atual` leem dessa mesma tabela —
a primeira itera os campos, a segunda valida que o campo pertence ao tipo antes de
serializar. Isso materializa INC-02 (dizer *quais* campos faltam) e a decisão de
design 3 do `design.md` (campos explícitos, não "qualquer zero") em um único lugar.
Se `_CAMPOS` fosse derivada dos defaults das colunas (`mapped_column(default=0)` em
`StockItem`/`Supplier`/`TransportRecord`), `quantidade` e `ativo` entrariam na
verificação e o sistema marcaria todo item recém-importado como incompleto. A
escolha de uma allow-list também torna os campos **não** verificados (`sku`,
`fornecedor_id`, `codigo_rastreio`, `quantidade`, `ativo`) uma consequência
estrutural, não uma lista negra que alguém esquece de atualizar.

**2. "Ausente" depende da natureza do campo, e não de um único teste de vazio.**

O helper `_ausente(valor, natureza)` encapsula as três regras do design: texto é
ausente quando `not str(valor or "").strip()` (vazio ou só espaços); inteiro quando
`int(valor or 0) <= 0`; decimal quando `float(valor or 0.0) <= 0.0`. A proteção
`valor or <default>` é defensiva contra `None`, ainda que as colunas atuais sejam
não-nuláveis e sem migration de nulabilidade (o design explicitamente evita mexer
nesse contrato). O ponto de negócio é que a *mesma* função `_ausente` decide
`nome` (texto) e `minimo` (inteiro) sem que `minimo=0` e `local=""` sejam tratados
como o mesmo "vazio" — é a granularidade que evita o falso positivo que corromperia
a fila. O teste `test_zero_legitimo_e_booleano_nao_sao_ausentes` fixa o outro lado
da moeda: `quantidade=0`, `ativo=False` e `avaliacao=0.1` não geram item.

**3. `valor_atual` serializa em string canônica e é um contrato de integração, não um
detalhe de apresentação.**

`valor_atual` usa `_serializar(valor, natureza)`: `str()` para texto, `str(int(...))`
para inteiro e `str(float(...))` para decimal. Essa string é o **snapshot** gravado em
`ItemCorrecao.valor_no_pedido` (T1) e re-calculada na aprovação para detectar
conflito (EDG-02): se o valor atual serializado divergir do snapshot, o item é
encerrado como `falhou` sem sobrescrever (`design.md` §"Aprovação, aplicação e
auditoria", passo 5). A consequência prática é que a T4 (`sugestoes.sugerir`) precisa
serializar `valor_sugerido` na mesma forma canônica — `"7"` para `prazo_dias=7`,
`"4.5"` para `avaliacao=4.5` — senão a comparação de no-op da EDG-05 (sugestão igual
ao valor atual → `aplicado` sem escrita) falharia por diferença de formato. Deixar
essa serialização dentro do domínio, em vez de espalhá-la pelas rotas web, é o que
mantém a comparação determinística.

**4. Tipo ou campo fora da tabela falha alto, com erro de domínio nomeado.**

`campos_faltantes` e `valor_atual` recusam entradas fora da allow-list com
`TipoCorrecaoInvalido` e `CampoCorrecaoInvalido` (subclasses de `ValueError`), em vez
de devolver `[]`, um `KeyError` cru ou um `AttributeError`. A justificativa é de
segurança operacional: um `tipo` digitado errado na camada de serviço (T5) ou um
`campo` que não é corrigível nunca deve virar silenciosamente "nada a corrigir" —
isso faria uma correção passar batido. Ao mesmo tempo, **não** foi criado um
`Literal` para o tipo: `Route`/`SpecialistName` em `state.py` enumeram os mesmos
nomes, e um novo enum aqui seria a segunda fonte de verdade condenada pela lição
L-013. A validação em runtime, contra as próprias chaves de `_CAMPOS`, mantém uma
fonte só e uma mensagem de erro explícita.

**5. A ordem dos campos é a ordem do design e está pinada por teste.**

`campos_faltantes` devolve os campos na ordem de inserção de `_CAMPOS`, que segue a
tabela do design (`nome`, `minimo`, `local`; `nome`, `categoria`, `prazo_dias`,
`avaliacao`; `origem`, `destino`, `peso_kg`, `status`). O docstring registra essa
dependência e `test_estoque_lista_todos_os_campos_faltantes_na_ordem_do_design` a
trava, para que uma reordenação acidental — que mudaria a apresentação da fila
(INC-02) — não passe despercebida.

**6. Os testes ficam na fronteira criada (`tests/correcoes/`) e cobrem vazio, zero e
valor legítimo.**

`tests/correcoes/test_completude.py` cobre os três tipos, os casos de vazio/zero e o
caso oposto (zero legítimo), além da serialização de valor ausente e da recusa de
tipo/campo desconhecidos. O self-review acrescentou
`test_campos_de_identidade_e_contagem_nao_entram_na_completude`, que pinica a regra
"identidade e contagem fora" com campos de identidade **vazios** — os fixtures
anteriores os mantinham preenchidos (`sku="SKU-1"`, `fornecedor_id="F-1"`,
`codigo_rastreio="BR-1"`), então a exclusão era implícita. A regra agora tem teste
próprio, sem tocar a lógica de produção.

## 3. Trade-offs & Compromissos

- **Texto é serializado cru (`str()`), então um campo só-espaços não vira `""`.**
  `_ausente` normaliza com `strip()`, mas `_serializar` devolve o texto como está,
  fiel ao design (`str()` para texto). A consequência é que o snapshot de um `nome`
  com `"   "` fica `"   "` e não `""`. É aceitável porque a comparação de conflito
  usa o mesmo `_serializar` dos dois lados: valor inalterado continua igual, e
  qualquer mudança real de conteúdo (incluindo espaços) gera conflito — que é o
  comportamento conservador desejado na EDG-02. Normalizar aqui poderia mascarar uma
  reimportação que alterou o valor.

- **Sem validação em runtime de que `tipo` e `registro` combinam.** A união
  `Registro` é uma anotação de tipo, não um guard; chamar `campos_faltantes("estoque",
  fornecedor)` levantaria `AttributeError` ao alcançar um campo exclusivo. Optou-se
  por não adicionar um mapa `tipo -> modelo` nesta task porque a T5 (serviço de fila)
  já precisa desse mapa para resolver o alvo e vai centralizar essa validação; adiantá-
  lo aqui duplicaria a responsabilidade. O erro é alto e não silencioso, que é o
  requisito de segurança do momento.

- **Sem tratamento de `NaN`/`inf` em campos decimais.** `nan <= 0.0` e `inf <= 0.0`
  avaliam para `False`, ou seja, contariam como valor presente. O design não previu
  esse caso, as colunas são `Float` alimentadas pela importação (que valida o
  payload), e tratar `NaN` exigiria um teste e uma semântica de negócio não
  decididos. Fica registrado como limitação e não como comportamento implícito.

- **`valor_atual` é mais restrita que `campos_faltantes`.** A primeira recusa campo
  desconhecido com `CampoCorrecaoInvalido`; a segunda nunca recebe campo (itera a
  tabela). A assimetria é intencional: `valor_atual` é chamada pela T7 com o campo
  vindo de dados persistidos, e uma divergência ali é um sinal de corrupção de
  estado que deve aparecer, não ser ignorada.

## 4. Limitações Conhecidas

- **O mapa `tipo -> modelo` e a validação de pareamento ficam para a T5.** Enquanto
  isso, um par `(tipo, registro)` trocado falha com `AttributeError`, não com um erro
  de domínio específico. A T5 é o ponto natural para fechar essa lacuna, pois já
  resolve alvo e repositório por tipo.
- **`NaN`/`inf` em `avaliacao`/`peso_kg` são tratados como presentes.** Se a
  importação passar a permitir esses valores, `_ausente`/`_serializar` precisam de uma
  regra explícita (e teste) para não gerar item nem conflito incorretos.
- **A lista de campos não verificados é documental, não declarada.** Ela existe por
  omissão da allow-list (por design, para não haver duas listas); quem ler só o código
  entende a exclusão pela ausência em `_CAMPOS` e pelos testes de identidade/contagem.
- **A serialização canônica é um contrato verbal entre T3 e T4.** Nada no tipo
  garante que a sugestão da T4 use a mesma forma; a integração é verificada pelos
  testes de no-op/conflito da T5/T7 no mesmo épico.
- **Cobertura de linha de `completude.py` é 100%**, mas os caminhos de `None` em
  `_ausente`/`_serializar` não são exercitados (colunas não-nuláveis); são defesa
  contra evolução futura do schema, não comportamento observado hoje.
