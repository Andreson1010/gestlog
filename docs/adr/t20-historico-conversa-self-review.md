# ADR: t20-historico-conversa

## 1. Contexto & Objetivo

As tasks T17–T19 entregaram o motor do copiloto, o endpoint SSE e a tela de chat,
mas a conversa inteira vivia apenas no DOM: ao recarregar a página, tudo sumia.
Essa era a última lacuna do critério **COP-06** (também o **AC 4** da história
P1 "Recomendação explicada"): *"WHEN a conversa avança THEN o sistema SHALL
manter o histórico do usuário no tenant e recuperá-lo ao voltar"*. Para o
operador, isso significa poder sair e voltar que o que já foi perguntado e
respondido continua ali; para o produto, é a base sobre a qual os aceites da T22
e a auditoria da T24/T25 vão se apoiar, porque a partir daqui existe uma
`Conversation` real à qual `Recommendation` e `Feedback` podem se prender.

O desafio arquitetural central não é gravar duas linhas no banco, e sim **onde
colocar a escrita sem quebrar as fronteiras do pacote** (`apps → agents → libs`,
AD-012): o serviço do copiloto vive em `copilot/` (camada `apps`), os dados vivem
nos repositórios (`libs`) e a página vive em `web/` (`apps`). Além disso, um
turno de chat não pode virar dois: a pergunta e a resposta precisam ser gravadas
como uma unidade, no tenant e no usuário corretos, mesmo que a resposta demore.

## 2. Decisões de Arquitetura

**1. Uma conversa por par `(empresa_id, user_id)`, resolvida por
`ConversationRepository.get_or_create`**

O MVP não tem tela de "múltiplas conversas"; então a solução mais direta e
previsível é manter **uma** `Conversation` por usuário em cada empresa e
acrescentar mensagens nela a cada turno. `get_or_create(empresa_id, user_id)`
primeiro tenta `get_by_user`, que filtra **as duas colunas** no SQL, e só cria
quando não existe. Isso torna a recuperação ao voltar determinística (a mesma
conversa é sempre encontrada) e evita que a página precise orquestrar estado de
conversa ativa. O filtro por `empresa_id` **e** `user_id` é o que garante o
isolamento: nada vem do cliente, os dois ids saem da sessão autenticada.

**2. O `CopilotService` passa a exigir `user_id` e persiste o turno como parte da
resposta: `registrar_turno`**

Antes, `answer(pergunta)` era puramente funcional. Agora o serviço recebe
`user_id` (campo obrigatório da dataclass) e, depois de rodar o grafo, chama
`registrar_turno`, que grava a pergunta como papel `"user"`, a resposta como
`"assistant"` e faz `commit`. Colocar a escrita no serviço — e não na rota —
mantém a regra de negócio "todo turno respondido é um turno guardado" em um único
lugar, reutilizável por qualquer entrada (web agora, REPL/CLI depois), e deixa a
rota apenas como adaptador HTTP. O `commit` fecha a unidade transacional: ou as
duas mensagens entram juntas, ou nenhuma entra, de modo que nunca há um histórico
com pergunta sem resposta por falha na segunda inserção.

**3. O histórico é lido como `list[Turno]`, agrupando mensagens em pares**

Para a tela, o que interessa não é a lista crua de `Message`, e sim a sequência de
perguntas e respostas. `carregar_historico` busca a conversa do usuário e delega a
`_montar_turnos`, que percorre as mensagens em ordem e produz uma lista de
`Turno(pergunta, resposta)` (`dataclass` imutável). Essa camada de leitura separa
o formato do banco (`Message`, com `papel` e `conteudo_redigido`, já preparado
para a redação de PII da T24) do formato de apresentação, então a T21 pode
acrescentar recomendação/fontes ao turno sem que o template mude de estrutura. Um
`Turno` sem resposta parceira vira `Turno(pergunta, "")`, garantindo que a tela
nunca quebre em um estado intermediário.

**4. A página renderiza o histórico no servidor (Jinja), sem JavaScript extra**

`GET /chat` carrega os turnos e os entrega ao template, que itera com
`{% for turno in turnos %}`. A alternativa — buscar o histórico por uma chamada
HTMX adicional — exigiria um segundo endpoint e um segundo formato de payload
(JSON) só para pintar a tela inicial. Renderizar no servidor reaproveita
exatamente o mesmo visual do turno ao vivo (`chat_turno.html`), mantém a tela
funcional mesmo com o JS desabilitado e não custa uma requisição a mais. O
caminho dinâmico (HTMX/SSE da T19) continua intacto: a tela nasce preenchida e os
novos turnos são anexados em `#conversa`.

**5. `get_current_empresa_optional`: página decide o login, API continua 401**

A página `/chat` precisa distinguir "sem sessão, manda pro login" (303) de
"com sessão, mostra o histórico" (200) — e uma dependência que exige empresa
devolveria `403` no meio do caminho. Criei `get_current_empresa_optional`, que
reusa `current_active_user_optional` e uma `_buscar_membership` extraída de
`get_current_membership` (a mesma ordenação determinística por
`created_at, id`), devolvendo `None` sem usuário ou sem vínculo. Assim o
comportamento das páginas HTML permanece 303 → `/login`, enquanto o endpoint SSE
`/chat/stream` continua `401` (contrato da T18 preservado: um `EventSource` não
pode receber o HTML de login como se fosse stream). A extração de
`_buscar_membership` eliminou a duplicação da query de vínculo entre as três
dependências.

**6. Isolamento por transparência: o histórico é exibição, nunca contexto do LLM**

O histórico é renderizado apenas para o operador; ele **não** é realimentado no
grafo a cada nova pergunta. Isso é deliberado: como o conteúdo armazenado nasce
de entrada do usuário e de saída do LLM (influenciável por prompt injection),
reinseri-lo no contexto criaria um vetor de injeção persistente. Manter o grafo
*stateless* por turno elimina essa superfície sem custo — a T21 que decidir se e
como usar contexto multi-turn, com as defesas adequadas. Enquanto isso, a
exibição passa pelo autoescape do Jinja (nenhum `| safe`), então HTML vindo da
resposta é mostrado como texto.

## 3. Concessões e Escolhas Práticas (Trade-offs)

- **Histórico não vira memória do copiloto:** cada pergunta é respondida sem
  conhecer os turnos anteriores. O AC 4 pede *manter e recuperar* o histórico, não
  dar contexto ao modelo; usar multi-turn fica para quando houver uma decisão de
  segurança/avaliação (T21+). Aceitável e mais seguro neste momento.
- **`get_or_create` não é atômico:** sem uma restrição única em
  `(empresa_id, user_id)` na tabela `conversation`, duas primeiras perguntas
  simultâneas do mesmo usuário podem criar duas conversas e dividir o histórico
  (uma delas some da página, que sempre pega a mais antiga). É uma corrida de
  janela mínima no MVP de um operador; resolver exige `UniqueConstraint` +
  migração, fora do escopo desta task. Registrado como limitação.
- **Limite de 4000 caracteres por mensagem (`String(4000)`):** perguntas longas
  ou respostas extensas do LLM podem estourar o tamanho no Postgres e virar
  `500` (o SQLite dos testes não impõe o limite, então a suíte não pega). A T21
  vai reestruturar a saída (recomendação/fontes) e a T24 cuidará de redação e
  retenção; endurecer o limite (truncar ou migrar a coluna para `Text`) entra
  junto, para não decidir sozinho agora o que é dado válido de histórico.
- **`commit` dentro do serviço:** o `CopilotService` encerra a transação, o que
  acopla a regra de negócio ao banco e assume que a sessão da requisição é
  exclusiva do turno — premissa verdadeira hoje (`get_sync_session` injeta uma
  sessão por request). Trocar por um *unit of work* na camada web seria
  refatoração maior sem ganho imediato.
- **Usuário sem vínculo vê página vazia:** se um usuário autenticado não tem
  `Membership`, `/chat` responde `200` com histórico vazio (o `empresa` opcional
  é `None`) e o `/chat/stream` responde `403` só quando o primeiro turno for
  enviado. O caminho de criação de conta do produto sempre cria vínculo, então o
  estado é de borda; tratar com onboarding/redirect fica para a task de admin.
- **Ordenação depende de timestamp:** `Message` não tem coluna sequencial, então
  o pareamento pergunta/resposta ordena por `created_at` e usa `id` como
  desempate. Com timestamps distintos (o normal) a ordem é de inserção; em
  empates, o desempate é estável, mas não necessariamente a ordem real. Uma
  coluna monotônica ou um `turno_id` explícito resolveria de vez, adiado por
  escopo.

## 4. O que vem a seguir (Roadmap Imediato)

- **T21 (Recomendação, fontes e insuficiência):** estruturar a resposta como
  recomendação + justificativa + fontes e persistir `Recommendation` na
  `Conversation` que esta task criou; a `Turno`/`_montar_turnos` foi desenhada
  para acomodar isso sem quebrar a tela.
- **T22/T23 (Feedback aceitar/descartar):** agora que existe conversa persistida,
  o `Feedback` pode apontar para a recomendação real; a UI ganha botões por turno
  no contêiner de conversa.
- **T24/T25 (PII, auditoria e uso):** a redação de PII passa a agir sobre o
  `conteudo_redigido` que esta task começou a gravar; é também onde o limite de
  tamanho, a retenção e a telemetria de uso serão tratados.
- **Infra do chat:** reavaliar a unicidade de `(empresa_id, user_id)` em
  `conversation` e a estratégia de ordenação das mensagens; mover
  `get_sync_session` de `ingestion_ui.py` para um `web/deps.py` (débito herdado
  da T13/T18/T19).

## 5. Validação de Qualidade e Segurança

- **Garantias de negócio e privacidade:** a recuperação sempre filtra
  `empresa_id` **e** `user_id` no banco, ambos resolvidos da sessão — nenhum id
  vem do cliente. Testes de unidade provam o isolamento entre empresas e entre
  usuários (`test_historico_isola_entre_empresas`,
  `test_historico_isola_entre_usuarios`) e um teste de integração faz a mesma
  prova via HTTP, criando duas empresas/usuários e verificando que a página de B
  não contém a pergunta nem a resposta de A (`test_historico_nao_vaza_entre_empresas`).
  A tela renderiza conteúdo persistido apenas com autoescape do Jinja, sem
  `| safe`.
- **Cobertura e testes automatizados:** a task adiciona 8 testes — 3 de unidade
  no serviço de copiloto para persistência/acúmulo/isolamento, 1 no repositório
  (`test_conversation_get_or_create_reutiliza_conversa`), 1 de unidade para o
  turno órfão (`test_historico_monta_turno_de_pergunta_sem_resposta`) e 2 de
  integração na UI (`test_pagina_chat_exibe_historico_apos_pergunta`,
  `test_historico_nao_vaza_entre_empresas`). Gate final: **139 passed**, cobertura
  **97,58%** (gate de 80%), com `copilot/service.py`, `repositories/conversations.py`,
  `web/chat.py` e `web/chat_ui.py` em **100%**.
- **Padrões de qualidade:** `black --check src/ tests/` → 72 arquivos
  inalterados; `ruff check src/ tests/` → All checks passed. Nomes de código em
  português (`pergunta`, `resposta`, `papel`, `conteudo_redigido`), docstrings em
  português e nenhum teste tocando rede/Ollama (modelo fake).

## Achados corrigidos no self-review

- **Ordenação de mensagens sem desempate (baixa):**
  `MessageRepository.list_by_conversation` ordenava apenas por `created_at`; com
  timestamps iguais o pareamento de turnos ficaria instável. Passou a ordenar por
  `(created_at, id)`, alinhado a `ConversationRepository.get_by_user` e
  `_buscar_membership`.
- **Cobertura do turno órfão (baixa):** a linha defensiva de `_montar_turnos`
  que trata pergunta sem resposta não era exercitada; novo teste de unidade
  `test_historico_monta_turno_de_pergunta_sem_resposta` cobre o caso e leva
  `copilot/service.py` a 100%.
- **Docstring desatualizada (informativa):** o cabeçalho de `web/chat_ui.py`
  indicava apenas T19; passou a citar T19/T20.
