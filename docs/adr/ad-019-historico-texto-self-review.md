# ADR: ad-019-historico-texto

## 1. Contexto & Objetivo

Três débitos da sessão de privacidade/tech-debt de 2026-10-28 (D2, D3, D4)
atacavam o mesmo ponto por ângulos diferentes: o **histórico de conversa** —
a espinha dorsal do copiloto, da qual saem a tela do chat, o agrupamento em
turnos (`Turno` em `copilot/service.py`) e as decisões de registro (aceitar/descartar) que alimentam os KPIs.

**D2** — o conteúdo redigido (`message.conteudo_redigido`) e o texto das
recomendações (`recommendation.texto`) estavam travados em `String(4000)`.
No dia em que um turno real exceder esse teto, o uso não fica "apertado":
o Postgres rejeita a gravação e o turno do operador é perdido no meio do
fluxo. Nenhum requisito de produto justifica o limite — conteúdo de turno é
tamanho desconhecido por construção (resposta do LLM, justificativa,
transcrição), e `TEXT` vs `VARCHAR(n)` no Postgres não tem custo de
desempenho; a única diferença é o guard.

**D3** — a ordenação do histórico dependia de `created_at` capturado por
`datetime.now()` no momento da gravação. No Windows, a resolução do clock
empata com frequência para gravações a milissegundos de distância (exatamente
o caso fonte de `user` → resposta `assistant` → recomendação gravada logo
após). O desempate por `id` (UUID aleatório) embaralhava turnos: a mesma
conversa podia aparecer em ordem diferente entre acessos, e
`_montar_turnos` — que intercala `Message` e `Recommendation` por
`created_at` — podia anexar a recomendação ao turno errado ou arrastá-la de
um turno anterior. O flake já havia se manifestado nos testes localmente
antes de virar decisão de arquitetura.

**D4** — os botões de aceitar/descartar só apareciam após recarregar a
página: o turno ao vivo era entregue por SSE (`T18/T19`), mas o fragmento de
feedback era renderizado apenas na passada sem estado do histórico. O
operador tomava a decisão a tempo, mas num fluxo dois cliques atrás do que
o produto promete.

O objetivo único desta entrega é fazer o histórico do turno ao vivo ser
**correto (ordem estável), sem teto (Text) e completo (botões no ato)** —
três mudanças que se sustentam mutuamente: sem o carimbo da D3, o turno ao
vivo da D4 pode receber o fragmento da recomendação errada; sem o Text da
D2, o turno longo falha na própria gravação.

## 2. Decisões de Arquitetura

**1. `Text` por migração de batch, com par de colunas como constante única
(D2)**

`models.py` troca `String(4000)` por `Text` nas duas colunas, e a migração
`d5e6f8a2b7c4` (downstream de `b7d2e9a4f108`) faz o `alter_column` via
`batch_alter_table` — escolha forçada pelo dialeto de teste: SQLite não
executa `ALTER COLUMN` direto, e o modo batch recria a tabela copiando os
dados, funcionando identicamente no Postgres. O par
`(("message", "conteudo_redigido"), ("recommendation", "texto"))` vive numa
única constante `_COLUNAS`, compartilhada por `upgrade()` e `downgrade()`
simétricos: a meia-linha que mais daria errado de forma assintomática (uma
coluna convertida e a outra esquecida) fica impossível por construção.
O teste de migração semeia a conversa completa (empresa, usuário, linha em
cada tabela), sobe até a revisão anterior, grava **5000 chars** em cada
coluna após o `upgrade` (prova de que o teto foi de fato removido — no
Postgres isso falharia contra `VARCHAR(4000)`, ou seja, o teste valida o
efeito e não só o tipo), lê os valores de volta e confere o tipo via
inspector em ambos os sentidos — uma asserção por coluna em `upgrade` e
`downgrade`, conforme L-037.

**2. Carimbo monotônico por conversa, tomado sobre Message e
Recommendation (D3/AD-019)**

A função `_carimbo_monotonico(session, conversation_id)` em
`repositories/conversations.py` substitui o `created_at` cru no
`add_message` e no `add_recommendation` (os dois únicos gravadores). Ela
consulta o `max(created_at)` de **Message** **e** de **Recommendation** da
conversa — consultá-las separadamente e comparar é o que garante a
invariante "estritamente crescente por conversa" na presença da
intercalação: os dois gravadores escrevem as duas tabelas, e o turno só se
fecha direito se o carimbo da recomendação for estritamente posterior ao da
resposta ou estritamente anterior à pergunta seguinte. Se o último
carimbo conhecido empata ou ultrapassa o agora do clock, soma-se 1
microssegundo; caso contrário, o agora é adotado (sem deslocar o relógio
para frente sem necessidade — o deslocamento só acontece quando há
colisão real). O desempate por `id` permanece no `ORDER BY` (regra vigente
do produto), mas desmorona ao caso "nunca acontece": carimbos distintos por
construção. Duas proteções blindavam a função: `valor.tzinfo is None →
replace(tzinfo=UTC)` (datetime relido do SQLite volta naive — L-031) e o
teste com `_RelogioTravado` (`monkeypatch` no `datetime` do módulo),
que grava usuário → resposta → recomendação → pergunta → resposta **sem
um único tick de clock** e exige cinco carimbos distintos e ordenados —
exatamente a sequência que produzia o flake.

**3. Fragmento público único e evento `fontes` no stream do turno (D4)**

O HTML dos botões não pode ser renderizado em dois lugares com regras
divergentes — nada pior para o operador do que aceitar na tela ao vivo e
ver a decisão "desaparecer" no reload. O `web/feedback.py` passa a expor
`fragmento_feedback(recommendation_id, decisao)`, usado tanto pela rota de
feedback (resposta POST que troca o fragmento com `hx-swap="outerHTML"`)
quanto pelo stream. Em `web/chat.py`, `_fragmento_do_ultimo_turno` pede o
último `Turno` recém-persistido ao `CopilotService.historico()` e emite o
fragmento no evento `fontes`; estando esse evento **condicional** (`if
fragmento`), os turnos sem recomendação (fora de escopo/insuficiente)
ficam sem botões por decisão de domínio, não por acidente. O cálculo do
fragmento fica no ramo `else` do `answer`, com `try/except` próprio: (i)
erro do copiloto → resposta de fallback **sem** fragmento (nada novo há
para decidir); (ii) resposta OK, mas falha ao montar o fragmento → o turno
mantém a resposta e perde só os botões, que voltam a existir no próprio
reload — o log pega o evento para investigação. Fragmento carrega
`decisao=None`: dois botões habilitados e "Sem decisão", estado correto
para a recomendação recém-criada.

**4. Escopo SSE no ancestral comum (achado do self-review, D4)**

A primeira montagem colocava `sse-swap="fontes"` num div **irmão** do
elemento com `sse-connect`. Lendo o código-fonte da extensão
(`htmx-ext-sse` 2.2.2, `registerSSE`/`ensureEventSourceOnElement`): o
elemento encontra a fonte **subindo a ascendência**
(`getClosestMatch(elt, hasEventSource)`) — um irmão é órfão por definição —
e o fan-out de eventos do htmx 2.0.4 (`Un`) só entrega o
`htmx:afterProcessNode` à extensão se houver `hx-ext="sse"` na ascendência
do elemento. Ou seja: os botões nunca chegariam à tela, e o teste SSE
(exclusivamente server-side) não teria como flagrar. A correção segue o
padrão documentado da extensão: `hx-ext="sse"` + `sse-connect` +
`sse-close="fim"` sobem para `.agente` — ancestral comum de `.resposta`
(`sse-swap="resposta"`, `hx-swap="textContent"`) e do novo
`.feedback-ao-vivo` (`sse-swap="fontes"`, `hx-swap="innerHTML"`) — e o
teste de UI (`test_turno_abre_assinatura_sse`) passa a fixar `hx-ext="sse"`
e `sse-swap="fontes"` na tela. A ordem dos eventos é garantida pelo servidor
(`resposta` → `fontes` → `fim`): os botões chegam antes do
`sse-close` fechar a assinatura.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **Downgrade com guard, não com truncamento:** restaurar `String(4000)` com
  conteúdo maior no banco seria executar `UPDATE` truncante ou deixar o
  Postgres fazer `ERROR: value too long` no meio da reversão. A escolha
  **foi** falhar alto: truncamento silencioso destrói conteúdo do usuário e
  a migração reversa é saída de emergência, não caminho de rotina. O teste
  semeia valor curto antes do `downgrade` e o valida de volta — o cenário
  "dado longo + downgrade" é deliberadamente não suportado (e documentado
  aqui como contracaso).
* **Duas `SELECT`s de `max` por gravação, com indexes por conversa:** a
  alternativa era uma única query com `UNION`. O custo extra é uma
  roundtrip por mensagem/recomendação por turno — tabela de conversa
  individual é pequena, e o caminho já paga `flush` na mesma conexão. A
  versão em duas queries é idiomática, tipada e cobre cada modelo
  separadamente nos testes.
* **Serialização de carimbo no Python, não no banco:** dois processos
  gravando a mesma conversa **concorrentemente** ainda poderiam empatar
  (ambos leem o mesmo último carimbo). Hoje a conversa pertence a um único
  usuário por sessão; quando isso mudar, a evolução natural é `SELECT ...
  FOR UPDATE`/sequence do banco, e o contrato `_carimbo_monotonico` é onde
  a troca acontece.
* **Custo de drift:** carimbo pode andar alguns microssegundos à frente do
  relógio real em conversas de gravação intensiva — ordenação relativa
  continua correta; o valor absoluto continua legível em auditoria e KPI
  (agregações usam `feedback.created_at`, não o carimbo).
* **Evento `fontes` carrega os botões, não a lista de fontes técnica:** o
  nome é parte do contrato já público da T18 (o painel técnico de fontes
  vem do turno completo no reload do histórico); reutilizar o mesmo canal
  evita inventar um segundo canal de stream para a mesma conexão.

## 4. O que vem a seguir (Roadmap Imediato)

* **PR D5+D6+D7 (AD-015):** rate limit (login/onboarding/convites),
  convite por token e empresa ativa via cookie; evals no CI. Já em WIP
  desta sessão, separado propositalmente deste PR.
* **Débitos herdados restantes:** `UniqueConstraint(empresa_id, user_id)` em
  `conversation`, mover `get_sync_session` para `web/deps.py` e remover o
  `TOOLS` mock do REPL quando houver banco — item permanece `[ ]` no
  `STATE.md` (ajuste feito no self-review, ver Achados).
* **Concorrência no carimbo:** migrar `_carimbo_monotonico` para guarda de
  banco (`FOR UPDATE` ou sequence por conversa) quando a escrita paralela
  na mesma conversa existir de fato.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio/privacidade:** o fragmento emitido por SSE só
  carrega `recommendation_id` e estado de decisão — nenhuma PII a mais do
  que a rota de feedback já expunha; a gravação da decisão continua pela
  rota POST autenticada com a guarda de tenancy (`get_do_usuario`, 404
  indeterminável); o carimbo altera apenas ordenação interna, não conteúdo
  auditável; turnos sem recomendação ficam sem botões por regra de domínio.
* **Cobertura e testes automatizados:** aceitação da sessão anterior nesta
  exata árvore: **591 passed** no SQLite (gate WSL2) e **591 passed** na
  matriz Postgres, 98,94% de cobertura — o gate não foi reexecutado no
  self-review por instrução; CI do PR valida o subconjunto commitado.
  Testes novos do diff: `test_migracao_conteudo_para_text` (dupla coluna,
  upgrade + downgrade com valor de 5000 chars),
  `test_carimbo_monotonico_desempata_clock_travado` (`_RelogioTravado`,
  5 carimbos distintos sem tick de clock),
  `test_carimbo_monotonico_usa_clock_quando_nao_empata`,
  `test_chat_stream_emite_fragmento_de_feedback_ao_vivo`,
  `test_chat_stream_sem_recomendacao_nao_emite_fontes`, além das asserções
  de tela (`hx-ext="sse"`, `sse-swap="fontes"`) em `test_chat_ui.py`.
* **Padrões de qualidade:** `black --check` + `ruff check` verdes nos
  arquivos tocados; `from __future__ import annotations`, docstrings em
  português, sem comentários fora de docstring, funções ≤ 50 linhas. A
  migração é o único `.py` novo do PR (nenhum arquivo de código novo além
  dela).

## Achados corrigidos no self-review

* **`sse-swap="fontes"` fora do escopo da fonte SSE (HIGH):** botões nunca
  renderizariam no turno ao vivo — div irmão do `sse-connect`, sem
  `hx-ext="sse"` na ascendência; o elemento fica órfão no `getClosestMatch`
  e o evento nunca chega (`getSelectors` processa, mas o fan-out do htmx
  2.0.4 não entrega `afterProcessNode` à extensão). Corrigido em
  `chat_turno.html` (fonte sobe para `.agente`, ancestral comum) e fixado
  em `test_chat_ui.py`. Lição registrada em **L-046**.

* **Checkbox parcial no `STATE.md` (média):** "Débitos técnicos herdados"
  marcado `[x]` com 3 dos 5 débitos ainda pendentes — recaída da L-044 em
  forma de subitem. Corrigido para `[ ]` com lista residual e nota dos
  subdébitos quitados. Lição registrada em **L-045**.
* **Parâmetro morto em `_carimbo_monotonico` (baixa):** a assinatura
  recebia `modelo`, mas o corpo sempre varre Message **e** Recommendation —
  o parâmetro sugeria algo que não era verdade. Removido (com o alias
  `_ModeloConversa`) e os dois call sites atualizados.
* **Asserção de virada de ano no teste do carimbo (baixa):**
  `nova.created_at.year == datetime.now(UTC).year` era a mesma classe de
  flake que a feature combate, em outra escala. Substituída por janela
  fechada `antes <= created_at <= depois`, robusta à resolução do clock.
* **Paridade do downgrade no teste de migração (baixa, L-037):** o teste
  conferia o tipo restaurado mas não o dado lido de volta; acrescentada
  asserção de conteúdo ("curto") por coluna após o `downgrade`.
