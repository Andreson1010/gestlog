# ADR: t23-feedback-ui

## 1. Contexto & Objetivo

A T22 fechou o contrato de escrita do gesto de aceitar/descartar: o endpoint
`POST /recomendacoes/{id}/feedback` persiste uma linha de `Feedback` (decisão,
usuário, tenant e timestamp) e já tinha a autorização provada por teste. Faltava
o lado visível do critério **COP-04/COP-06**: o operador precisava ver as *fontes*
que embasaram a recomendação e os botões que registram a decisão **na própria
tela de chat**, sem que cada clique provocasse um recarregamento de página — a
condição de pronto é literalmente *"aceite/descarte refletem sem recarregar
(HTMX)"*.

O desafio não estava na tela em si, mas no **pareamento**. Desde a T21 a
`Recommendation` guarda apenas `conversation_id`: não existe chave estrangeira
ligando a recomendação à mensagem/turno que a originou. Um botão precisa de um
`recommendation_id` para apontar o `hx-post`, e a tela precisa de uma decisão
vigente para desabilitar o botão já escolhido. Sem migration — decisão de desenho
aprovada em sessão: *"pareamento na leitura, sem migration"* — a solução foi
reconstruir essa associação no momento de ler o histórico, intercalando mensagens
e recomendações em ordem cronológica. O objetivo desta task, então, foi um
componente de UI enxuto sobre um pareamento determinístico e de baixo custo.

## 2. Decisões de Arquitetura

**1. Pareamento na camada de leitura, sem migration**

`carregar_historico` monta os turnos em `_montar_turnos(mensagens,
recomendacoes, decisoes)`. Em vez de alterar o schema para ligar recomendação e
turno, o serviço combina as duas listas em um único fluxo de eventos ordenado por
`created_at` e anexa cada recomendação ao turno que a precede
(`turnos[-1] = replace(turnos[-1], ...)`). A justificativa de produto é o custo de
mudança: um FK exigiria migration Alembic, backfill de dados já gravados e uma
alteração de escrita em `registrar_turno`; o pareamento por tempo entrega o mesmo
resultado visível com uma função pura e testável. O `Turno` ganhou
`recomendacao_id`, `fontes` e `decisao` com **valores padrão**
(`None`/`()`), então os consumidores anteriores — a renderização da T19/T20 e a
comparação por igualdade em `test_historico_monta_turno_de_pergunta_sem_resposta`
— continuam funcionando sem adaptação.

**2. Desempate determinístico: mensagem antes de recomendação**

A ordenação usa a tupla `(created_at, tipo, id, objeto)`, com `tipo == 0` para
`Message` e `tipo == 1` para `Recommendation`. O motivo é prático: no mesmo
`registrar_turno`, pergunta, resposta e recomendação são gravadas em sequência, e
o relógio do sistema pode devolver o mesmo `created_at` para duas gravações
consecutivas. Se o desempate fosse o `id` (UUID aleatório), uma recomendação que
empatasse com a sua resposta poderia ser ordenada **antes** dela e acabar anexada
ao turno anterior — ou descartada, se ainda não houvesse turno. Colocar o `tipo`
antes do `id` garante que mensagens definam o turno primeiro e que a recomendação
"do mesmo instante" caia no turno certo, de forma independente do sorteio do UUID.
O `null`-safety está garantido porque `tipo` sempre difere antes de o ORM objeto
ser comparado.

**3. Decisão vigente calculada na leitura: "última linha vence"**

O fragmento mostra a decisão atual e desabilita o botão já escolhido. Como o
`Feedback` é *append-only* (cada clique insere uma linha; a T22 já registrava
"última linha vence" para os KPIs), a leitura precisa reduzir o histórico à
decisão vigente. `FeedbackRepository.latest_by_conversation(conversation_id)`
faz um `JOIN` de `Feedback` com `Recommendation`, filtra pela conversa ordenando
por `created_at, id` e sobrescreve um dicionário `{recommendation_id: decisao}` —
a última iteração de cada recomendação é a que fica. O efeito para o operador é
direto: aceitar e depois descartar reflete o descarte, sem apagar a trajetória que
a auditoria e a T32 querem preservar.

**4. O endpoint da T22 passa a devolver um fragmento HTML (200), não JSON (201)**

`registrar_feedback` responde com `HTMLResponse` renderizado por `_feedback.html`,
um fragmento com o rótulo da decisão, o formulário `hx-post` para
`/recomendacoes/{id}/feedback`, `hx-target`/`hx-swap="outerHTML"` e os botões
Aceitar/Descartar (o vigente `disabled`). O HTMX troca apenas o próprio bloco,
sem recarregar a página — que é exatamente a condição de pronto da task. A troca
de contrato é legítima e **delegada pela própria T22**: a *Decisão 4* e o
trade-off *"Resposta JSON em vez de fragmento HTML"* da ADR da T22 registram
explicitamente que "a T23 decide se troca esse JSON por um fragmento visual".
Nenhum consumidor além dos testes do endpoint lê o JSON antigo; a mudança de 201
para 200 é consistente com uma resposta de swap. A autorização permanece
inalterada: `RecommendationRepository.get_do_usuario` continua resolvendo
`empresa` **e** `usuario` a partir das dependências de sessão antes de qualquer
escrita, e o 404 por indistinção é preservado. O fragmento é renderizado por
Jinja com `autoescape` (o `Jinja2Templates` do Starlette 1.6 usa
`select_autoescape()` para `.html`), e `_render_feedback` **não** usa `| safe`:
fontes e decisão são dados do servidor (a decisão é validada como
`Literal["aceita", "descartada"]`), sem reintroduzir XSS.

**5. `latest_by_conversation` no repositório, reutilizável pela T32**

A redução "última decisão por recomendação" não ficou no serviço nem na rota,
mas no `FeedbackRepository`, junto de `list_by_recommendation`. Assim a mesma
regra de negócio que a tela usa agora será reaproveitada pela agregação de KPIs
da T32 no futuro, sem duplicação. Como na T22, o repositório confia na resolução
prévia da conversa (que carrega `empresa_id`/`user_id`) para o isolamento; o
`JOIN` com `Recommendation.conversation_id` é o que amarra o conjunto à conversa
correta.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **Uma consulta extra por carregamento de histórico:** `carregar_historico`
  agora executa três consultas (mensagens, recomendações e decisões vigentes) em
  vez de uma. `latest_by_conversation` traz todas as linhas de `Feedback` da
  conversa e reduz em memória, porque uma janela `ROW_NUMBER()` portável entre
  SQLite e o banco de produção era complexidade desnecessária no volume do MVP.
  Um `JOIN` indexando `feedback.recommendation_id` fica no radar da T32, quando a
  agregação por período crescer.
* **Pareamento por tempo, não por chave:** a associação recomendação↔turno
  depende de `created_at` refletir a ordem de gravação. É aceitável porque
  `registrar_turno` grava pergunta, resposta e recomendação **no mesmo fluxo
  síncrono**, encostadas no tempo; o desempate por `tipo` cobre o empate real
  (recomendação × sua própria resposta). O que ainda escapa é uma anomalia de
  relógio (passo do NTP para trás) ou dados editados manualmente; se o produto
  precisar de pareamento à prova de auditoria, um `turno_id`/`message_id` com FK
  será a próxima conversa — e aí uma migration se justifica.
* **Decisão vigente não é imposta pelo banco:** `latest_by_conversation` calcula
  a última decisão na leitura; não há `UniqueConstraint` nem `upsert`. Mantém a
  trilha append-only exigida pela T22 e a simplicidade, ao custo de transferir a
  regra para o consumidor — que está documentada no repositório e coberta pela
  tela.
* **CSRF herdado, não introduzido:** o endpoint é POST que altera estado com
  autenticação por cookie. O `CookieTransport` usa `cookie_samesite="lax"`, que
  não envia o cookie em POST cross-site, e a task não adiciona um novo endpoint.
  Um token anti-CSRF continua sendo uma decisão de escopo amplo (login,
  importação), não desta task; fica registrado para o hardening do épico.

## 4. O que vem a seguir (Roadmap Imediato)

* **T33 (aceitação P1):** o fluxo ponta a ponta recomendar → aceitar → recarregar
  e ver o registro fecha COP-04/COP-06 junto com o histórico da T20. É o teste
  que prova o pareamento da leitura num cenário de uso real.
* **Task futura (paridade do turno ao vivo via SSE) — limitação documentada:**
  o turno recém-perguntado é montado por `chat_turno.html`, que abre o SSE e
  renderiza apenas o texto da resposta; ele **não** recebe `recommendacao_id` nem
  `fontes`, então os botões só aparecem no próximo carregamento de `/chat`. Isto
  está dentro do escopo declarado ("1 componente") e é aceitável para a F1, mas é
  uma lacuna de UX deliberadamente adiada: o próximo passo é o stream da T18
  carregar um evento final com a recomendação (id + fontes + decisão) e disparar
  `hx-trigger` para injetar o fragmento sem reload. Deve ser uma task própria de
  refinamento da UI, não um alargamento silencioso desta.
* **T32 (Dashboard de KPIs):** reutiliza `latest_by_conversation` (ou uma
  variante por período) para contar a última decisão por recomendação, e não o
  total de linhas, respeitando o contrato append-only.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio e privacidade:** o fragmento só é emitido depois de a
  recomendação ser autorizada contra `empresa.id` **e** `usuario.id` resolvidos
  da sessão; nenhum id de tenant/usuário vem do cliente. O histórico de leitura
  parte da conversa do usuário logado, então recomendações de outro tenant ou de
  outro usuário nunca chegam ao HTML. A resposta é autoescapada pelo Jinja, sem
  `| safe`, e a decisão é validada por `Literal` — sem reintrodução de XSS nem
  injeção de HTML por fontes/estado. Não há chamada a LLM nem envio de dado a
  provedor externo nesta task.
* **Cobertura e testes automatizados:** `tests/copilot/test_service.py` ganhou
  dois testes de integração (recomendação anexada com a última decisão; pareamento
  no turno certo quando um turno anterior foi de insuficiência) mais um teste de
  regressão determinístico do desempate de timestamp
  (`test_montar_turnos_anexa_recomendacao_em_empate_de_timestamp`).
  `tests/web/test_feedback.py` atualizou o contrato para 200 + HTML e cobre a
  tela exibindo fontes/botões e o fragmento refletindo a decisão. Execução focada:
  **26 passed**. Gate completo: **157 passed**, cobertura **97,76%** (gate de
  80%), com `web/feedback.py` e `web/chat_ui.py` em **100%**.
* **Padrões de qualidade:** `uv run python -m black --check src/ tests/` → 74
  arquivos inalterados; `uv run python -m ruff check src/ tests/` → All checks
  passed. Docstrings e nomes em português (`_montar_turnos`, `decisao`, `fontes`),
  `from __future__ import annotations` presente, nenhum comentário fora de
  docstring, nenhum `print`, funções bem abaixo de 50 linhas.

## Achados corrigidos no self-review

* **Desempate por UUID na intercalação (média-alta):** a tupla de ordenação
  `(created_at, id, ...)` usava o `id` aleatório antes do tipo. Medição local
  mostrou que `datetime.now(UTC)` tem resolução de ~1,3 µs, então duas gravações
  consecutivas podem empatar; nesse caso a recomendação podia ser ordenada antes
  da própria resposta e ser anexada ao turno anterior (ou descartada). A chave
  passou a ser `(created_at, tipo, id, objeto)`, forçando mensagem antes de
  recomendação no empate. Foi adicionado o teste de regressão
  `test_montar_turnos_anexa_recomendacao_em_empate_de_timestamp`, que falharia na
  implementação anterior.
* **"Fontes:" órfão quando a lista é vazia (baixa):** `chat.html` imprimia o
  rótulo mesmo sem fontes. O bloco passou a ser guardado por
  `{% if turno.fontes %}`, evitando um rótulo solto caso uma recomendação chegue
  sem fontes por inconsistência de dados.
* **Sem achados** de lint, formatação, tipagem, segredo hardcoded, vazamento de
  dado entre tenants, XSS (autoescape confirmado) ou `print` além dos acima.
* **Observação registrada, não bloqueante:** CSRF por cookie é herdado dos
  endpoints existentes e mitigado por `SameSite=Lax`; um token anti-CSRF é
  hardening de escopo mais amplo, fora da T23.
