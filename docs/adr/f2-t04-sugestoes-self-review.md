# ADR: f2-t04-sugestoes

## 1. Contexto & Objetivo

A T4 entrega o cérebro determinístico da fila HITL da F2: `src/gestlog/correcoes/sugestoes.py`,
com `Sugestao(campo, valor, justificativa, fonte)` e
`sugerir(tipo, campo, registro, contexto) -> Sugestao`. Ela se apoia nas duas peças
anteriores — a tabela de completude (T3) e o repositório escopado (T2) — e alimenta o
serviço de fila (T5), que materializa os itens pendentes. O resultado prático para o
operador é direto: para cada campo que falta no cadastro, ele recebe um valor sugerido,
uma justificativa e a fonte do dado — ou a marcação explícita de "sem sugestão", nunca
um valor inventado.

O desafio arquitetural não é "calcular uma média", e sim **produzir uma recomendação
auditável e reprodutível a partir de dados que podem estar incompletos**. Três tensões
governam a task: (a) **determinismo** — a mesma base de registros tem de produzir
sempre a mesma sugestão, senão a aprovação humana deixa de ser confiável e o teste,
impossível; (b) **honestidade estatística** — quando não há base, o correto é não
sugerir, porque um valor inventado seria uma escrita sem fundamento entrando na fila;
e (c) **reuso sem divergência** — a sugestão precisa ser serializada na *mesma* forma
canônica que a T3 usa para o valor atual, pois é isso que permite ao serviço detectar
no-op e conflito (EDG-05, EDG-02) sem duas tabelas de serialização que possam divergir.

## 2. Decisões Arquiteturais

**1. O determinismo é um requisito de primeira classe, e cada estratégia tem uma regra
de desempate explícita.**

Cada campo tem uma estratégia declarada em `_ESTRATEGIAS`: `moda` (valor textual não
vazio mais frequente), `mediana_inteiro` (mediana dos valores `> 0`) e `media_decimal`
(média dos valores `> 0`, uma casa). Em empate de frequência, `_moda` não devolve "algum
dos mais frequentes": filtra os empatados e aplica `min(...)`, fixando o **menor
lexicográfico**. Na mediana de lista par, `_mediana_inteiro` usa
`floor((a + b) / 2 + 0.5)` — a média dos dois centrais **arredondada para cima**
(*half-up*), e não o arredondamento bancário do Python. A justificativa é de produto e
de engenharia ao mesmo tempo: como a sugestão vira um item que um humano vai aprovar e
o sistema vai testar, um resultado que "depende da ordem de leitura do banco" seria
irreprodutível. Os testes `test_moda_desempata_por_ordem_lexicografica`,
`test_mediana_inteiro_com_quantidade_par_arredonda_para_cima` e
`test_sugerir_e_deterministica_para_os_mesmos_dados` fixam exatamente essas bordas, para
que uma troca de implementação não mude o resultado em silêncio.

**2. Sem base, a sugestão é explicitamente vazia — nunca um valor inventado.**

`_sem_sugestao` devolve `valor=None`, `fonte=""` e a justificativa
`"sem base de dados no tenant"`. Dois caminhos chegam lá: o campo não tem estratégia
(`fornecedores.nome`, `estoque.nome`, `transporte.peso_kg` — identidade ou dado
específico do registro, que não se infere dos irmãos) e a amostra é vazia (todos os
demais registros têm o campo ausente/zero, ou não há demais). Isso materializa SUG-03:
o sistema **marca** o campo como não preenchível em vez de preencher. A consequência
para o fluxo HITL é que o item continua na fila para decisão consciente, mas só pode ser
**rejeitado** — aprovar sem valor seria uma escrita sem conteúdo (a T7 devolve 409).
Colocar os campos sem estratégia *fora* de `_ESTRATEGIAS` torna a "sem sugestão" uma
consequência estrutural da ausência na tabela, e não uma lista negra que alguém esquece
de atualizar.

**3. A serialização do valor sugerido é delegada à T3, a única fonte de verdade do
formato; não há uma segunda tabela de campos.**

`sugerir` devolve `valor=serializar(tipo, campo, valor)` e valida a entrada com
`natureza(tipo, campo)` — ambas as funções públicas extraídas de
`correcoes/completude.py`. A razão é a integração: o `ItemCorrecao` guarda
`valor_no_pedido` (snapshot do valor atual, via `valor_atual`) separado de
`valor_sugerido` (via `serializar`), e a aprovação compara os dois para decidir no-op
(EDG-05) ou conflito (EDG-02). Se a T4 montasse o texto do número por conta própria —
`"4.30"` em vez de `"4.3"`, por exemplo — a comparação de igualdade falharia por
formato e o sistema trataria um no-op como conflito. Manter uma tabela só (`_CAMPOS`,
com a natureza de cada campo) é o que evita a segunda fonte de verdade condenada pela
lição **L-013**. A validação via `natureza` antes de qualquer `getattr` também preserva
a ordem de avaliação da **L-016**: campo desconhecido levanta `CampoCorrecaoInvalido`,
não `AttributeError`.

**4. As tabelas indexadas por `(tipo, campo)` são as únicas listas do módulo, e a
paridade entre elas é testada, não presumida.**

`_ESTRATEGIAS` (o que calcular) e `_FONTES` (o rótulo legível da origem) são indexadas
pela mesma chave `(tipo, campo)`. O risco óbvio desse desenho é uma estratégia sem fonte
ou uma fonte órfã após uma edição — exatamente o tipo de divergência silenciosa que a
L-013 alerta. Por isso o self-review adicionou `test_estrategias_fontes_e_campos_sem_orfaos`,
que afirma `set(_FONTES) == com_estrategia` **e** que toda chave de estratégia aponta
para um campo real de `_CAMPOS` (via `natureza`). O efeito é que adicionar um campo novo
sem atualizar as duas tabelas (ou apontar para um campo inexistente) quebra a suíte na
hora, em vez de virar um `_fonte` vazio em produção. Nenhum `Literal`/enum foi criado
para `tipo`/`campo`: a tabela de completude já é a fonte única desses nomes.

**5. `sugerir` é uma função pura: o contexto é parâmetro, e o alvo é excluído por
identidade.**

`sugerir` não toca banco nem repositório; recebe `contexto` (os registros do mesmo tipo
no tenant) e filtra o próprio alvo com `outro is not registro`. Isso mantém o domínio
puro e testável sem rede/DB — o teste unitário passa a lista na mão — e deixa a
responsabilidade de buscar e escopar os irmãos por empresa com a T5, que já resolve o
alvo por tipo e trabalho. O isolamento por tenant não desaparece: ele continua sendo
garantido na camada que monta o `contexto`, que só pode conter registros do
`empresa_id` da sessão.

**6. A cobertura de testes é paramétrica e varre os três tipos, não só os casos
exemplares.**

Além dos 13 testes (15 instâncias) do builder, o self-review acrescentou
`test_todo_campo_com_estrategia_gera_sugestao`, parametrizado sobre **todos** os pares
`(tipo, campo)` de `_ESTRATEGIAS`, que monta um alvo com o campo ausente (vazio/zero
conforme a natureza) e exige valor, justificativa e fonte. Isso fecha a lacuna de
cobertura: antes, `transporte.destino`, `transporte.status` e outros campos só eram
cobertos indiretamente por compartilharem o mesmo corpo. O arquivo passou de 15 para 24
casos, mantendo `tests/correcoes/test_sugestoes.py` espelhando a fronteira criada.

## 3. Trade-offs & Compromissos

- **A média usa `round` do Python, que é bancário (para o par mais próximo), e não
  half-up como a mediana.** São determinísticos os dois, mas podem divergir no empate
  `.x5`: a média de `4.2` e `4.3` é `4.25`, e `round(4.25, 1)` devolve `4.2`, não `4.3`.
  Foi aceito porque o design especifica apenas "média (1 casa)" — sem regra de
  arredondamento — e a diferença é de `0.1` numa nota de avaliação, imaterial para a
  decisão humana. A inconsistência com a mediana (half-up) é consciente e está
  registrada como limitação; um `valor` `nan`/`inf` também não tem semântica definida e
  herda o comportamento da T3.
- **O `n` das justificativas/fontes é o tamanho da amostra de valores válidos, não o
  total do contexto.** Para os numéricos isso é obrigatório para a frase fazer sentido
  ("mediana dos `prazo_dias` acima de zero entre 3 registros" — os `> 0`). Para a moda
  textual, "entre N registros" então exclui os vazios. A leitura é defensável (são os N
  candidatos considerados), mas há um efeito estético quando N = 1: a frase fica
  `"entre 1 registros"` no plural. Preferiu-se não pluralizar nem separar as contagens
  para não introduzir uma segunda noção de "quantidade" no módulo.
- **A exclusão do alvo é por identidade de objeto (`is not`), não por chave natural
  (PK/`sku`/`fornecedor_id`/`codigo_rastreio`).** É o contrato certo para o domínio puro
  — o teste constrói os objetos e passa `[alvo, *demais]` — e evita que objetos ainda
  sem `id` (antes do flush) sejam todos tratados como iguais. O custo é que a T5 não pode
  reidratar o alvo numa segunda instância e passá-lo no contexto: ela precisa passar a
  mesma instância (ou pré-filtrar o contexto). A exclusão por chave natural fica como
  evolução se o serviço pedir; hoje seria um mapa `tipo -> campo de identidade` que a
  T5/T3 ainda não têm.
- **Estratégia é string, e o despacho em `sugerir` trata "não moda e não mediana" como
  média.** Como `_ESTRATEGIAS` é interno e o teste de paridade o trava, hoje não há
  valor inválido. Ainda assim, um typo futuro (`"media_deciml"`) seria lido como média
  no despacho (e como numérico em `_valores`), sem erro alto. Não foi endurecido com
  `Literal`/mapa de handlers porque a checagem estática não roda no gate (só `ruff`) e
  a tabela é pequena e testada; fica registrado como limitação.

## 4. Limitações Conhecidas

- **Empate `.x5` da média arredonda para o par (bancário).** `4.25 → "4.2"`. Se o
  produto quiser half-up para a avaliação média, é trocar `round` por uma função
  explícita e fixar com teste; a mudança é local e não afeta a serialização.
- **Despacho por string de estratégia sem guard de runtime.** Um valor fora das três
  estratégias cairia no *else* (média). A proteção é o teste de paridade + revisão;
  um `Literal`/mapa de handlers é a evolução natural quando a checagem estática entrar
  no CI.
- **Exclusão do alvo por identidade de objeto.** Depende de a T5 passar a mesma
  instância; um contexto reidratado pode incluir o próprio alvo e enviesar moda/mediana.
  A chave natural (identidade do registro) é a alternativa robusta.
- **Volume do `contexto` é O(n) por sugestão, em memória.** `sugerir` varre todos os
  irmãos do tenant para cada campo faltante. Com muitos itens incompletos, o custo por
  item cresce com o tamanho do tenant; a T5 pode agregar/limitar a amostra, e a EDG-08
  (paginação) é sobre a listagem, não sobre a geração.
- **A integração no-op/conflito com T7 ainda é um contrato verbal.** `serializar`
  compartilhado garante o formato, mas nada no tipo força a T5/T7 a usá-lo; a prova
  chega com os testes de aceitação da T12.
- **`nan`/`inf` em campos decimais são tratados como presentes** (herdado da T3):
  `nan > 0` e `inf > 0` são `False`/`True` conforme o caso e não há regra de negócio
  definida. Se a importação passar a permitir esses valores, a amostra precisa de um
  filtro explícito com teste.
- **`tests/correcoes/test_sugestoes.py` alcança símbolos privados (`_ESTRATEGIAS`,
  `_FONTES`) para travar a paridade.** É a forma direta de pinçar a invariante
  "sem órfãos"; a alternativa (exercitar todos os campos públicos) já está coberta pelo
  teste paramétrico, mas não detectaria uma fonte órfã de campo sem estratégia.

## 5. Validação de Qualidade e Segurança

- **Garantias de negócio:** nenhuma sugestão é inventada — `valor=None` cobre campo sem
  estratégia e amostra vazia (SUG-03); toda sugestão carrega valor, justificativa e fonte
  com o dado que a sustenta (SUG-02); o alvo é excluído da própria base (SUG-01) e a
  função é pura, sem acesso a banco, preservando o isolamento por tenant na camada que
  monta o contexto.
- **Cobertura e testes automatizados:** `tests/correcoes/test_sugestoes.py` com 24
  casos (15 originais + 9 do self-review), incluindo os testes paramétricos de todos os
  campos e o de paridade/órfãos. Gate focado `uv run pytest tests/correcoes --no-cov`:
  35 passed. Suíte completa: **322 passed, 98,47%** (gate de 80% ok).
- **Padrões de qualidade:** `uv run black src/gestlog/correcoes tests/correcoes` e
  `uv run ruff check src/gestlog/correcoes tests/correcoes` verdes; `from __future__
  import annotations` em todos os módulos; docstrings em português; sem comentários
  fora de docstring.
