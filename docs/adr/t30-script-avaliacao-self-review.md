# ADR: t30-script-avaliacao

## 1. Contexto & Objetivo

A T29 entregou a régua de qualidade do copiloto — o golden set declarativo e o
runner `run_golden_set` — mas deixou uma lacuna prática: até então não havia como
*operar* essa régua contra o modelo real. Sem esse passo, o requisito **QUA-01**
("o sistema reporta acurácia, alucinação e fonte correta") continuaria provado
apenas contra um modelo fake em CI; ninguém conseguiria medir, no dia a dia, se a
versão real do `LLM_MODEL` estava acertando por domínio, nem guardar esse retrato
como evidência de qualidade.

A T30 fecha essa lacuna com uma CLI que carrega `evals/golden_set.json`, executa o
grafo contra o modelo configurado no `.env` e grava/imprime um relatório com a
acurácia por domínio. O desafio de arquitetura não é a lógica em si — ela já existe
e é testada na T29 — e sim separar o que precisa ser testável em CI (a montagem do
relatório, sem rede) do que é uma operação manual e sensível (o disparo contra
Ollama/endpoint real), para que essa separação não volte a acoplar a suíte rápida a
dependências externas.

## 2. Decisões de Arquitetura

**1. Lógica testável no pacote (`evaluation/script.py`) e launcher fino em `evals/`**

A primeira decisão foi onde colocar o quê. Toda a lógica — `gerar_relatorio`,
`salvar_relatorio` e o `main` — vive em `src/gestlog/evaluation/script.py`, dentro
do pacote importável, coberto por `tests/evaluation/test_script.py`. A pasta
`evals/` recebe apenas `run_golden_set.py`, um launcher de 12 linhas que importa
`main` e o chama sob `if __name__ == "__main__":`. A separação importa por dois
motivos práticos: um script top-level em `evals/` não é importável de forma limpa
para teste e não faria parte do pacote instalado; já a lógica em `gestlog.evaluation`
é exercitada com o `FakeChatModel` de `tests/conftest.py`, sem rede e sem custo,
entrando no gate rápido de CI. O launcher é deliberadamente descartável e não
duplica nenhuma regra — se um dia a operação mudar, muda-se `script.py`, e o
launcher nunca precisa saber.

**2. Injeção do modelo com default real, para testar sem construir rede**

`gerar_relatorio(caminho_golden, model, settings)` aceita um `BaseChatModel`
opcional; só quando ele é `None` a função chama `build_chat_model(settings=...)`
para instanciar o modelo real apontado para o endpoint compatível com OpenAI do
`.env`. Isso preserva o mesmo contrato de injeção já usado em `build_graph` e em
`run_golden_set` (T29): os testes passam o fake e o caminho ficou 100% offline;
o operador, rodando `uv run python evals/run_golden_set.py`, não passa nada e
recebe o modelo real. O `settings` também é injetável (`settings or get_settings()`),
o que evita depender do `.env` no teste e mantém `max_tool_steps` e `recursion_limit`
vindo de configuração, nunca hardcoded.

**3. Relatório JSON com acurácia por domínio, serializável e determinístico**

`relatorio_para_dict` converte o `RelatorioAvaliacao` da T29 em um `dict` puramente
JSON — inteiros, floats, strings e listas (as tuplas de `fontes` viram `list`) —
incluindo os indicadores globais (acurácia, taxa de alucinação e de fonte correta) e
a lista `resultados` caso a caso, o que permite auditar exatamente qual pergunta
falhou. A acurácia por domínio é calculada por `acuracia_por_dominio`, que agrupa
pelo `dominio_esperado` de cada caso e joga os casos sem domínio (perguntas fora de
escopo, como "qual a capital?") na chave `fora_de_escopo`. O agrupamento é
determinístico: percorre `relatorio.resultados` na ordem e o `dict` resultante
preserva a ordem de primeira aparição, então dois runs idênticos produzem o mesmo
JSON. O destino padrão é `evals/relatorio.json`, que é um artefato gerado — não
versionado — e por isso foi adicionado ao `.gitignore`, evitando que uma execução
local contra o modelo real polua o diff do PR ou vaze conteúdo avaliado sem querer.

**4. Operação manual, não agendada, e intocada da suíte de testes**

O script foi desenhado como operação manual do time, não como rotina de CI nem
agendada. O motivo é custo e determinismo: rodar o golden set contra o modelo real
gasta tokens e depende de um serviço externo volátil, então ele não pode influenciar
o resultado do gate. Nenhum teste importa `evals/run_golden_set.py` nem chama
`main()`; o `main` inclusive é marcado `# pragma: no cover`, seguindo a convenção do
repositório para a borda de CLI. Assim, a suíte permanece rápida, offline e
determinística mesmo com o novo script no repositório.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **Caminhos default derivados de `Path(__file__).resolve().parents[3]`:** é a
  forma mais simples de achar a raiz do repositório (`src/gestlog/evaluation/` →
  `parents[3]` → raiz) e aponta corretamente para `evals/golden_set.json` e
  `evals/relatorio.json`, validado em execução. A limitação é que, se o pacote
  fosse instalado de forma não editável e o script executado de fora do repositório,
  `evals/` estaria em `site-packages` e não existiria. Aceitável para MVP: a CLI é
  explicitamente uma operação de repositório, executada via
  `uv run python evals/run_golden_set.py`, e o modo editable é o padrão do `uv sync`.
* **Saída em JSON bruto, sem formatação de painel:** `main` imprime apenas o caminho
  do arquivo, a acurácia geral e a acurácia por domínio, e delega a leitura detalhada
  ao JSON. É menos amigável do que uma tabela rica, mas mantém o script pequeno e o
  artefato consumível por qualquer ferramenta (jq, planilha, futura T31), sem
  acoplar a CLI a uma biblioteca de apresentação.
* **Sem argumentos de linha de comando:** o caminho do golden e o destino do
  relatório são os defaults; parametrizar via `argparse` seria escopo extra sem
  demanda na spec. As funções já aceitam `Path` como parâmetro, então adicionar flags
  no futuro é trivial, sem refactor.
* **Reuso integral do runner da T29:** o script não reimplementa execução nem
  cálculo — apenas orquestra `carregar_golden_set` + `run_golden_set` +
  `relatorio_para_dict`. Isso mantém uma única definição de acurácia e alucinação, o
  que evita que a nota do operador divirja da nota do teste.

## 4. O que vem a seguir (Roadmap Imediato)

* **T31–T33 (gestão admin, KPIs e aceitação P1):** os indicadores de acurácia,
  alucinação e fonte correta gerados aqui alimentam os painéis de qualidade e custo
  da operação; o JSON já nasce com granularidade por domínio e por caso para isso.
* **Ampliar o golden set:** novos casos por domínio entram apenas como dado em
  `evals/golden_set.json`, sem tocar no script — a interface da T29 foi desenhada
  para esse crescimento.
* **Automação opcional (futuro):** se houver demanda, um job agendado pode chamar
  `gerar_relatorio`/`salvar_relatorio` em ambiente controlado, mas isso depende de
  orçamento de tokens e de disponibilidade do endpoint, e por isso ficou fora da T30.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio e privacidade:** o relatório contém apenas identificadores
  de caso, domínio esperado/obtido, booleanos de acerto/alucinação e as fontes
  citadas — nenhum dado pessoal ou de tenant. O artefato `evals/relatorio.json` é
  ignorado pelo git, então a saída de uma execução real não é versionada por engano.
  O modelo real só é construído quando não há injeção, e apenas na operação manual.
* **Cobertura e testes automatizados:** `tests/evaluation/test_script.py` cobre
  acurácia por domínio com fake model, execução contra o `GOLDEN_PADRAO`, gravação
  do JSON e o agrupamento em `fora_de_escopo`. Gate focado
  (`tests/evaluation tests/copilot --no-cov`): **49 passed**. Gate completo anterior:
  **213 passed**, cobertura **98,10%**.
* **Padrões de qualidade:** `uv run python -m black --check src/ tests/ evals/` (91
  arquivos inalterados) e `uv run python -m ruff check src/ tests/ evals/` (All
  checks passed). `from __future__ import annotations` presente em todos os novos
  arquivos, nomes e docstrings em português, sem comentários fora de docstring, sem
  `print` fora da borda de CLI (`main`), funções muito abaixo de 50 linhas, uso de
  `pathlib` e nenhum valor de configuração hardcoded (modelo e limites vêm de
  `Settings`/parâmetros).

## Achados corrigidos no self-review

* **Nenhum deslize material encontrado:** a avaliação contra o `AGENTS.md` não
  identificou correção necessária. Foram verificados e confirmados: (a) os caminhos
  `GOLDEN_PADRAO`/`RELATORIO_PADRAO` resolvem para a raiz do repositório
  (`Path(__file__).resolve().parents[3]`, confirmado em execução); (b) o modelo real
  **não** é construído quando `model` é injetado (`model or build_chat_model(...)`);
  (c) `acuracia_por_dominio` e `relatorio_para_dict` são determinísticos e
  serializáveis (validado por `json.dumps`/`json.loads` nos testes); (d) o launcher
  `evals/run_golden_set.py` é fino, sem lógica duplicada; (e) `evaluation/script.py`,
  `relatorio.py` e o launcher começam com `from __future__ import annotations`, não
  têm `print` fora de `main` nem comentários fora de docstring.
* **Limitação registrada, não corrigida (leve, operacional):** execução fora do
  repositório com instalação não editável não encontra `evals/`. Documentada na seção
  3 como aceitável para o escopo, sem alteração de código.
