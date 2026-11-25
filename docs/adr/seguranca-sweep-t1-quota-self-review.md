# ADR: seguranca-sweep-t1-quota

## 1. Contexto & Objetivo

A varredura de segurança do épico **seguranca-sweep** apontou o achado **C-1
(CRITICAL)**: os tokens do supervisor nunca entravam na quota — o roteamento via
`with_structured_output` devolvia só `{"next": rota}`, e o consumo registrado
cobria apenas os especialistas. Como todo turno passa ao menos uma vez pelo
supervisor, a quota era estruturalmente furável: o custo real divergia do medido
em cada turno. A ela se somavam **I-7** (resposta sem `usage_metadata` — ou com
`total_tokens = 0` — registrava zero) e **I-8** (a sequência check→LLM→record
sem serialização permitia que dois turnos simultâneos da mesma empresa lessem a
mesma folga e ambos passassem).

A T1 fecha os três com os requisitos **QUO-01..06** e os edge cases
**EDG-01/02/03/11/12**, sem abrir escopo de produto: medir o que antes escapava,
estimar quando o provedor não reporta, e serializar o check/record por empresa —
mantendo a empresa B imune aos locks da A.

## 2. Decisões de Arquitetura

**1. Contagem de tokens por helper público com piso de estimativa (QUO-01/02)**

`_tokens_da_resposta` (privado, dos especialistas) virou
`tokens_da_mensagem(mensagem)` em `agents/base.py`, agora também usado pelo
supervisor. A regra única: usa `usage_metadata["total_tokens"]` quando presente
e **positivo**; caso contrário estima `max(1, len(texto) // 4)`. Dois detalhes
carregam o requisito: o `or 0` dentro do `int(...)` trata ausente/`None`/`0` da
mesma forma (EDG-11 — metadata zerada vira estimativa, não atalho para zero), e
o piso de 1 token garante que texto não vazio nunca meça zero. O supervisor passou
a criar o roteador com `include_raw=True` porque a versão "crua" de
`with_structured_output` devolve o `dict` com a `AIMessage` original — é dela que
os tokens do roteamento saem; o nó devolve `{"next", "tokens_usados"}` e o
reducer `operator.add` do `AgentState` acumula roteamentos + especialistas sem
mudar o contrato do grafo. Saída malformada (`parsing_error`/sem `parsed`) mantém
o comportamento de segurança anterior — `FINISH` — e ainda assim conta os tokens
da mensagem bruta: encerrar a conversa não pode apagar o custo dela.

**2. Serialização por lock pessimista de linha, não contador atômico (QUO-03)**

`EmpresaRepository.travar` carrega a linha com `SELECT ... FOR UPDATE` + `flush`
e a quota é validada contra essa instância travada; o `record_usage` escreve na
mesma sessão e o `commit` único do turno libera o lock. Preferimos o lock
pessimista a um `UPDATE empresa SET ...` atômico porque a fonte de verdade já é
`SUM(usage_record)` — um contador derivado criaria segunda fonte (e job de reset
mensal) para ganhar uma corrida que o lock resolve no banco. Em Postgres, o
perdedor da corrida espera no lock e re Lê o uso gravado pelo vencedor, sendo
bloqueado com a mensagem de quota; em SQLite o `FOR UPDATE` é no-op do driver,
mas o lock `RESERVED` do primeiro write mantém a semântica, e a prova física da
corrida fica no Postgres da matriz de dialetos (teste skipável sem a variável).
O lock é **por linha de empresa**: a A travada nunca segura o turno da B
(EDG-02), e não há segundo recurso no caminho do turno que crie ordem de
travamento — impossível deadlock por construção.

**3. A salvaguarda global entra DEPOIS do check por empresa (QUO-04/05)**

Com a coluna `empresa.token_quota_mensal`, o teto de `Settings` muda de papel:
deixa de ser a quota individual e vira o limite do **somatório mensal de todas
as empresas** (`check_teto_global`), aplicado após `check_quota` no mesmo fluxo
(`CopilotService._checar_quota`: trava → check por empresa → teto global). A
ordem importa: checar o somatório primeiro bloquearia a B pelo consumo da A —
exatamente o que EDG-02 proíbe — e checar a empresa primeiro dá o erro mais
específico (quota dela, não a global com `empresa_id` sentinela `UUID(int=0)`).
`NULL` na coluna herda o teto do `Settings` (decisão humana 1) e o consumo
histórico continua contando sem reset nem backfill (decisão humana 2, EDG-12) —
`check_quota` soma o mês inteiro, sem exceção para "antes da migração".

**4. O SQL vive no repositório; o metering orquestra**

`travar_empresa` em `copilot/metering.py` delega a
`EmpresaRepository.travar`, e `check_teto_global` lê via
`UsageRepository.total_geral_desde`. Nada de `select()` em `copilot/` ou
`agents/` — a direção de dependência `apps → libs` fica intacta e a consulta
com `with_for_update` é testável junto dos demais repositórios. A criação de
empresa passa a recusar `token_quota_mensal <= 0` com `ValueError` antes do
banco (QUO-04), espelhando o padrão da validação de `retention_days`.

**5. Migração mínima e reversível (QUO-04)**

`f1a2b3c4d5e6` (down `e8a1c5d9f3b7`) apenas adiciona
`empresa.token_quota_mensal` como `Integer` **nullable** — sem
`server_default`, porque `NULL` é semântica (herdar o global), não ausência de
dado. O teste faz o round-trip completo: coluna ausente antes, presente depois,
inserções com valor e com `NULL` lidas corretamente, e coluna removida no
downgrade **alvejando o pai** (`e8a1c5d9f3b7`) — a semântica "downgrade TO
revision" do Alembic, já registrada como lição L-052.

**6. O `FakeChatModel` fala o novo contrato antes de qualquer consumidor**

`with_structured_output` do conftest devolve `{"raw": AIMessage, "parsed":
RouteDecision}`, o shape real do `include_raw=True`. A atualização do conftest
foi pré-requisito deste PR (não follow-up) porque TODO teste de grafo consome o
contrato — deixá-lo velho quebraria a suíte inteira; o parâmetro extra
`**_` aceita a nova assinatura sem tocar os testes existentes.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **O lock da linha fica preso durante a chamada LLM.** É o custo deliberado de
  serializar check→LLM→record na mesma transação: a janela entre o check e o
  record é a própria chamada ao modelo. Só turnos da MESMA empresa disputam o
  lock — e serializá-los é exatamente o objetivo (I-8). A pendura indefinida é
  mitigada pelo `llm_timeout_s` da T6 (mesma integração; antes da T6 o risco de
  pendura já existia hoje, o lock apenas o torna visível por tenant).
* **A estimativa `len//4` é grosseira e conservative-biased.** Pode superestimar
  texto denso e subestimar/estourar em tokens CJK, mas a meta do requisito é não
  subestimar o uso (I-7) — erro para cima é aceitável de negócio, erro para
  abaixo é a fenda da quota.
* **A corrida real só é provada no Postgres.** Sem
  `GESTLOG_TEST_DATABASE_URL`, os dois testes de contenção pulam; o SQLite local
  prova a semântica (resolução de quota, bloqueio por soma), não a contenção
  física. Padrão da matriz de dialetos já assumido pelo repo (L-038).
* **O teto global usa o mesmo valor da quota por empresa.** Um único
  `Settings.llm_monthly_token_quota` serve aos dois papéis; separar os tetos
  criaria uma segunda configuração sem requisito que a peça.

## 4. Limitações Conhecidas

* **Corrida cross-tenant no teto global (aceita — L-2):** o lock é por linha de
  empresa, então o somatório do `check_teto_global` não é serializado — duas
  empresas simultâneas podem, juntas, atravessar o teto global antes de a
  salvaguarda perceber. A salvaguarda é aproximada por construção: serializá-la
  exigiria um lock global (toda empresa disputando o mesmo recurso), trocando
  isolamento por contenção cruzada — exatamente o que o EDG-02 proíbe. A
  revisão fica condicionada a um requisito de teto global exato.
* **Janela do lock depende da T6 (L-1):** o lock da linha da empresa fica preso
  durante a chamada LLM; sem `llm_timeout_s` (T6, mesmo release do épico), uma
  pendura do provedor mantém o lock indefinidamente para os turnos seguintes da
  MESMA empresa. A mitigação chega com a T6; a pendura pré-existia no código de
  hoje (sem lock), o lock apenas a torna visível por tenant.
* `check_teto_global` reporta a empresa sentinela `UUID(int=0)` na exceção — o
  bloqueio global não tem dono; a mensagem é genérica de propósito.
* A estimativa trata `content` multimodal (lista) pelo comprimento do `str` —
  aproximação, aceitável enquanto nenhum modelo do tenant devolve conteúdo rico.
* "um empresa" em docstrings antigas de `repositories/` (fora do diff) segue
  como dívida de concordância gramatical — apenas a linha regredida neste PR
  foi restaurada.

## 5. Validação de Qualidade e Segurança

* **Discriminantes provados contra a versão vulnerável:** revertendo
  temporariamente `agents/supervisor.py` para o `main` e rodando a suíte focada,
  `test_turno_so_supervisor_conta_tokens` falha com `assert 0 > 0` (C-1
  reproduzido), `test_supervisor_soma_tokens_do_roteamento` falha com
  `KeyError: 'tokens_usados'` e o roteamento nem chega ao especialista
  (`'FINISH' == 'estoque'`). Revertido de volta — working tree limpa.
* **Gate completo:** `uv run pytest` → **623 passed, 3 skipped**, cobertura
  **99,08%** (gate de 80%); `ruff check` → All checks passed; `black --check` →
  151 files unchanged. Nenhum teste toca rede/Ollama.
* **Padrões AGENTS.md:** `from __future__ import annotations` em todos os
  arquivos, funções abaixo de 50 linhas (o `answer_com_recomendacao` foi
  fatiado em `_checar_quota`/`_rodar_grafo`), docstrings em português, sem
  comentários fora de docstring, `logger` sem `print`, SQL confinado a
  `repositories/`.

## Achados corrigidos no self-review

* **Concordância regredida em docstring (leve):** o hunk da T1 trocou
  "tokens consumidos **pela** empresa" por "**pelo** empresa" em
  `repositories/telemetry.py::total_tokens_desde`. Restaurado
  (`d55e2e5`).
* **Docstring do `tokens_usados` defasada face à QUO-01 (leve):** `state.py`
  dizia que o reducer somava "os tokens reportados **pelos especialistas**" —
  agora também chegam roteamentos do supervisor. Atualizada para "por cada nó
  do grafo — roteamentos do supervisor e respostas dos especialistas"
  (`f667586`).
* **Sem demais achados:** nenhuma falha lógica fundamental, nenhuma violação de
  fronteira (SQL só em `libs`), nenhuma janela de corrida nova, migração com
  round-trip e asserção por efeito. A verificação empírica do discriminante
  substituiu o revert-and-run completo da suíte, que segue cara (~6 min) — o
  gate final completo cobre a regressão global.
