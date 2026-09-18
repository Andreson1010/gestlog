# ADR: t29-golden-set

## 1. Contexto & Objetivo

Depois de T24–T28, o copiloto do gestlog já responde com dados reais do tenant,
estrutura a recomendação, mede o consumo e bloqueia quota — mas nada mede se as
respostas estão **certas**. Sem uma régua de qualidade, não há como provar o
requisito **QUA-01** ("o sistema reporta acurácia, alucinação e fonte correta")
nem perceber regressões quando o prompt, o roteamento ou as ferramentas mudam. A
T29 entrega exatamente essa régua: um formato declarativo de casos de teste por
domínio e um runner que roda cada caso no grafo verdadeiro e agrega o resultado em
um relatório.

O desafio central não é "chamar o modelo e comparar texto" — isso seria frágil e
caro. É definir uma métrica que use o **mesmo** contrato que o runtime do copiloto
usa (a `Recomendacao` estruturada com texto, justificativa e fontes, da T21) e que
seja executável sem rede, com um modelo fake injetado, para entrar no gate de CI.
Esta task é deliberadamente só o núcleo e o formato: o script que roda contra o
modelo real é a T30.

## 2. Decisões de Arquitetura

**1. O golden set é dado declarativo em JSON; a lógica fica no código**

O conjunto é um arquivo `evals/golden_set.json` — uma lista de objetos com `id`,
`pergunta`, `dominio`, `fontes_esperadas` e `requer_recomendacao`. Manter os casos
como dado, e não como código Python, permite que um analista de operação acrescente
um caso real sem tocar no runner, versiona o conteúdo separadamente da mecânica e
mantém `src/gestlog/evaluation/golden.py` focado em interpretar, não em armazenar.
`carregar_golden_set(Path)` faz a validação na fronteira: rejeita raiz que não seja
lista, item que não seja objeto e campos com tipo errado (`fontes_esperadas` deve
ser lista de strings; `requer_recomendacao` deve ser booleano), convertendo tudo em
`CasoGolden`, uma dataclass `frozen` imutável. O dataset-semente cobre os três
domínios (estoque, fornecedores, transporte) justamente para que o runner seja
exercitado no caminho completo já nesta task.

**2. O runner roda o grafo de produção, mas com o modelo injetado**

`run_golden_set(casos, model, settings)` compila o grafo com `build_graph(model=...,
settings=...)` — o mesmo grafo supervisor + especialistas que o copiloto usa. Isso é
intencional: se o golden set testasse um caminho paralelo, ele mediria uma
realidade que não existe em produção. O que varia é apenas a **dependência externa
volátil**: nos testes passa-se o `FakeChatModel` de `tests/conftest.py` (fila de
rotas para o supervisor e fila de tool calls para os especialistas), e na T30
passar-se-á o modelo real. Nenhum teste toca rede/Ollama, então a avaliação entra
no gate rápido de CI sem custo nem flakiness. O parâmetro `settings` também é
injetável (`settings or get_settings()`), o que evita depender de `.env` no teste.

**3. As métricas reutilizam a interpretação do runtime, para não divergir**

O ponto mais importante de qualidade: `_avaliar_caso` não reinventa a leitura da
resposta. Ele chama `extrair_recomendacao(bruto, dominio)` — a mesma função que o
`CopilotService.answer` usa para decidir o que é recomendação, o que é insuficiência
e quais fontes foram citadas. Se o golden set tivesse sua própria heurística de
"o modelo respondeu?", ele poderia aprovar respostas que o produto rejeita (ou
vice-versa), tornando a métrica uma ficção. Reusar o extrator da T21 garante que a
nota mede o comportamento que o usuário realmente recebe.

As três métricas significam:
* **Acurácia** (`acuracia`): fração de casos em que o comportamento esperado
  ocorreu. Se o caso exige recomendação, acertou quem recomendou **e** roteou para
  o domínio certo; se o caso não exige recomendação, acertou quem não recomendou.
* **Alucinação** (`taxa_alucinacao`): fração de casos em que o sistema recomendou
  quando o caso **não** requeria recomendação. É a definição operacional de
  alucinação adotada: inventar uma resposta onde o correto era recusar por falta de
  base.
* **Fonte correta** (`taxa_fonte_correta`): fração de casos em que todas as fontes
  esperadas aparecem entre as fontes citadas pela recomendação. Em caso de recusa
  esperada, conta como correta quando não houve recomendação — ou seja, mede "não
  fabricou fonte", que é o modo de falha que essa métrica deve capturar.

As taxas são propriedades calculadas sobre `RelatorioAvaliacao` com guarda explícita
de divisão por zero (`... if self.total else 0.0`), de modo que um relatório vazio
devolve zeros em vez de estourar.

**4. A dependência `evaluation → copilot` é aceita e consciente**

`golden.py` importa `extrair_recomendacao` e `texto_resposta` de
`gestlog.copilot.service`. O `AGENTS.md` descreve as três fronteiras conceituais
(`apps → agents → libs`) e proíbe inversão de dependência; `evaluation` é um
arnês de qualidade que fica ao lado do `apps`, e depende de `copilot` para
reaproveitar o contrato de interpretação. A alternativa "pura" seria mover
`Recomendacao`/`extrair_recomendacao` para `agents`, mas isso tocaria o runtime da
T21 e seus testes sem entregar valor nesta task — exatamente o refactor grande que
a spec manda evitar. Reusar a função existente é mais seguro do que duplicar a
lógica, então a dependência foi aceita e documentada; se um dia a avaliação for
extraída para outro deploy, o caminho natural é promover o extrator a `agents`.

**5. Na fronteira, o helper privado virou público — sem quebrar a T17**

O runner precisava da função que varre `state["messages"]` e devolve a última
resposta (ou o aviso de fora de escopo). Ela vivia como `_texto_resposta`, privada.
Importar um símbolo privado de outro pacote é frágil: qualquer refactor interno do
copiloto quebraria a avaliação. A correção foi expor `texto_resposta` como API
pública em `copilot/service.py`, reexportá-la em `copilot/__init__.py` e manter
`_texto_resposta = texto_resposta` como alias de compatibilidade, para não quebrar
referências históricas da T17. O `CopilotService.answer` passou a chamar a versão
pública; o comportamento é idêntico.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **A alucinação é medida por "recomendou quando não devia", não por comparação de
  texto.** Um golden set com gabarito textual pegaria nuances de redação, mas seria
  caro de manter, frágil e exigiria um judge/LLM extra. A definição comportamental
  é objetiva, determinística e alinhada ao contrato de `Recomendacao`; o preço é
  não detectar uma recomendação factualmente errada desde que ela seja bem-formada
  e cite a fonte esperada. Aceitável no escopo de MVP: cobre os dois modos de falha
  que importam — rota errada e resposta inventada.
* **O dataset-semente é pequeno (3 casos).** Não é uma amostra estatística; é o
  andaime que prova o formato e o runner. A T30 e o trabalho de qualidade
  subsequente é que devem ampliar o conjunto por domínio.
* **`fonte_correta` exige que **todas** as fontes esperadas apareçam (`all(...)`),
  não que sejam as únicas.** Mede cobertura das fontes necessárias, não
  exclusividade; uma resposta que cita fonte extra ainda é considerada correta.
  Isso evita punir justificativas mais ricas.
* **Recusar conta como "fonte correta".** Em casos `requer_recomendacao=False`,
  `fonte_correta = not recomendou`. É uma escolha semântica: a falha de fonte nesse
  caso é fabricar uma referência, e não citar demais. Está documentado na docstring
  e no teste de alucinação.

## 4. O que vem a seguir (Roadmap Imediato)

* **T30 (Script de avaliação):** CLI que carrega `evals/golden_set.json`, injeta o
  modelo real, chama `run_golden_set` e salva/imprime o `RelatorioAvaliacao`. É o
  consumidor direto desta interface e não precisa mexer no núcleo.
* **T31–T33 (admin, KPIs, aceitação P1):** os mesmos indicadores de acurácia e
  alucinação alimentam os painéis de qualidade e custo da operação.
* **Ampliar o golden set:** novos casos por domínio conforme reais apareçam,
  sem alterar o runner — o formato declarativo foi desenhado para isso.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio e privacidade:** nenhum caso do dataset contém dado
  pessoal ou de tenant; o runner usa o grafo puro, sem sessão de banco, sem
  `CopilotService`, sem persistência e sem rede. A avaliação mede roteamento,
  recusa e citação de fontes, não vaza dados entre empresas.
* **Cobertura e testes automatizados:** `tests/evaluation/test_golden.py` cobre
  acurácia total, fonte errada, alucinação, relatório vazio, carga do arquivo,
  execução a partir do arquivo e rejeição de formato inválido (não-lista, item
  não-objeto, caso incompleto, tipos inválidos). Gate focado:
  `tests/evaluation tests/copilot tests/test_graph.py` → **48 passed**. Gate
  completo: **209 passed**, cobertura **98,07%**, com `evaluation/golden.py` em
  **100%**.
* **Padrões de qualidade:** `black --check` (87 arquivos inalterados) e
  `ruff check` (All checks passed). `from __future__ import annotations` presente,
  nomes e docstrings em português, sem comentários fora de docstring, sem `print`,
  funções abaixo de 50 linhas, dataclasses `frozen` e nenhum valor de configuração
  hardcoded (modelo e `recursion_limit` vêm de parâmetros/`Settings`).

## Achados corrigidos no self-review

* **Import de símbolo privado (`_texto_resposta`) entre pacotes (leve,
  acoplamento):** `evaluation/golden.py` dependia de um helper privado do copiloto.
  Exposta `texto_resposta` como API pública em `src/gestlog/copilot/service.py`,
  reexportada em `copilot/__init__.py`, com alias `_texto_resposta` preservando
  compatibilidade; o runner passou a importar a função pública. Comportamento
  inalterado.
* **Validação de fronteira incompleta no JSON (leve, robustez):** `_caso_de_dict`
  aceitava `fontes_esperadas` como string (viraria tupla de caracteres) e
  `requer_recomendacao` como string (`"false"` viraria `True`). Adicionada validação
  de tipo na fronteira, convertendo qualquer formato inválido no mesmo `ValueError`
  já previsto.
* **Branch sem cobertura em `golden.py` (leve, teste):** o caminho de recusa de
  item não-objeto e os de tipo inválido não tinham teste, deixando o módulo em 97%.
  Adicionados testes para item não-objeto, `fontes_esperadas` não-lista e
  `requer_recomendacao` não-booleano; `golden.py` passou a **100%**.
* **Sem demais achados:** nenhuma falha lógica ou de segurança fundamental. A
  definição de alucinação, o reuso do extrator da T21 e a dependência
  `evaluation → copilot` foram avaliados e mantidos, com justificativa nas seções 2
  e 3.
