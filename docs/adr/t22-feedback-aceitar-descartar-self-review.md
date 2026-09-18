# ADR: t22-feedback-aceitar-descartar

## 1. Contexto & Objetivo

A T21 fechou o ciclo de *recomendação explicada*: cada resposta suficiente do
copiloto vira uma linha de `Recommendation` com texto, justificativa e fontes,
presa a uma `Conversation` do usuário no tenant. Faltava o gesto que dá valor de
produto a essa recomendação — o operador aceitá-la ou descartá-la — e o dado que
alimenta os KPIs de aceitação do épico (KPI-01/T32). É o critério **COP-06**:
*"WHEN o operador aceita ou descarta THEN o sistema SHALL registrar a decisão com
usuário, tenant e timestamp."*

O `Feedback` já existia no modelo desde a fundação (`id`, `recommendation_id`,
`decisao`, `user_id`, `created_at`) e
`FeedbackRepository.add_feedback` já sabia inserir. O desafio desta task não foi
criar tabela nem algoritmo: foi **fechar a fronteira de autorização** de um
recurso que não carrega `empresa_id` próprio. A `Recommendation` só conhece a
conversa; a conversa é que conhece usuário e tenant. Registrar a decisão sem uma
checagem explícita seria abrir uma porta para qualquer id de recomendação de
qualquer cliente. A meta, então, foi um endpoint pequeno e verificável que
persiste a decisão **e** prova, por teste, que ninguém decide sobre a
recomendação de outro tenant ou de outro usuário.

## 2. Decisões de Arquitetura

**1. Autorizar pela conversa, exigindo empresa *e* usuário ao mesmo tempo**

O endpoint não aceita a recomendação "crua" do banco. Ele resolve
`RecommendationRepository.get_do_usuario(recommendation_id, empresa.id,
usuario.id)`, que faz um `JOIN` de `Recommendation` com `Conversation` e filtra
`Conversation.empresa_id == empresa_id` **e** `Conversation.user_id == user_id`.
Os dois ids vêm das dependências de sessão (`get_current_user`,
`get_current_empresa`) — nunca do corpo ou da URL —, então o cliente só escolhe
*qual* recurso, não *de quem* ele é. A exigência dupla não é excesso de zelo: no
MVP cada operador tem sua própria conversa
(`ConversationRepository.get_or_create(empresa_id, user_id)`) e só vê o próprio
histórico, portanto a recomendação exibida com botões é a que nasceu no turno
daquele operador. Restringir a autoria impede que um colega do mesmo tenant
decida sobre uma recomendação que não é dele e mantém a trilha
`Feedback.user_id` coerente com quem de fato clicou.

**2. 404 — e não 403 — para recurso inexistente ou alheio**

Quando `get_do_usuario` devolve `None`, a rota responde
`HTTP_404_NOT_FOUND` com `detail="Não encontrado."`, o mesmo contrato que
`verificar_empresa_do_recurso` já usa na base. A escolha é de segurança por
indistinção: se o endpoint diferenciasse "não existe" (404) de "existe, mas é de
outro" (403), um atacante conseguiria usar os códigos como oráculo para
enumerar ids de recomendações alheias. Com uma única resposta, o tenant que não
possui o recurso não aprende nada sobre a existência dele — e um id válido do
próprio usuário continua respondendo 201 normalmente.

**3. Feedback *append-only*: cada clique é um evento, não uma célula atualizada**

`add_feedback` insere uma linha nova a cada decisão; não há `upsert` nem
`UniqueConstraint`. O teste
`test_registra_aceite_e_descarte` fixa esse contrato ao aceitar e depois
descartar a mesma recomendação, esperando **duas** linhas `["aceita",
"descartada"]` do mesmo `user_id`. A motivação é de produto e de auditoria: a
decisão de um operador pode mudar de ideia (aceitou por engano, descartou em
seguida), e guardar a trajetória é mais fiel do que sobrescrever o passado. Para
que os KPIs não somem trocas de decisão, `list_by_recommendation` ordena por
`created_at, id` e a última linha é a decisão vigente — contrato que ficou
escrito no docstring e que a T32 deve respeitar ao agregar.

**4. Corpo `form`-encoded, resposta JSON 201 — prontos para o HTMX da T23**

A rota declara `decisao: Annotated[DecisaoFeedback, Form()]`, com
`DecisaoFeedback = Literal["aceita", "descartada"]` em `web/schemas.py`, em vez
de JSON. O motivo é o consumidor imediato: a T23 ligará os botões
aceitar/descartar com HTMX, que envia `application/x-www-form-urlencoded` por
padrão. Usar `Form()` agora evita um adaptador na próxima task e, de quebra,
deixa a validação de valor inválido a cargo do framework (422 antes de tocar o
banco). A resposta 201 devolve `{"feedback_id", "decisao"}`, um contrato de API
estável; a T23 decide se troca esse JSON por um fragmento visual.

**5. `list_by_recommendation` no repositório, com o contrato de escopo explícito**

A leitura das decisões entrou em `FeedbackRepository`, e não no endpoint, para
ser reutilizável pela agregação de KPIs da T32. Como `Feedback` não tem
`empresa_id`, o repositório não filtra tenant por conta própria — o mesmo
desenho de `MessageRepository`, que confia na resolução prévia da conversa.
Esse era um contrato implícito e virou explícito no docstring da classe, para
que nenhum consumidor futuro leia feedback sem antes autorizar a recomendação.

## 3. Concessões e Escolhas Práticas (Trade-offs)

- **Decisão vigente calculada, não imposta pelo banco:** não há
  `UniqueConstraint` em `recommendation_id` nem `upsert`. Isso deixa o histórico
  completo e mantém a T22 como gravadora, mas transfere para os consumidores a
  regra "última linha vence". É aceitável no MVP porque só a T32 agrega (a T23
  apenas emite a decisão) e o contrato está documentado no repositório; uma
  guarda de idempotência agora contradiria o requisito append-only e não traria
  benefício imediato.
- **Escopo por usuário, não por papel:** qualquer usuário autenticado com
  vínculo no tenant pode decidir, desde que a recomendação seja da própria
  conversa. Não há `exigir_papel(...)`, porque aceitar/descartar é ato do
  operador que recebeu a recomendação, não um ato administrativo. Se o produto
  passar a permitir que gestores decidam por terceiros, isso será uma mudança
  deliberada de escopo, com implicação de auditoria.
- **404 para usuário da mesma empresa sem posse:** um colega recebe "não
  encontrado" em vez de "sem permissão". Optou-se por não revelar existência a
  ninguém fora do dono; o custo é um suporte eventualmente menos óbvio, sem
  impacto funcional no MVP de conversa individual.
- **Resposta JSON em vez de fragmento HTML:** um fragmento seria mais direto
  para o HTMX, mas exigiria a T22 decidir a apresentação — que é escopo da T23.
  Preferiu-se manter a fronteira API/UI e deixar a T23 ser dona do HTML.
- **Índice em `feedback.recommendation_id` adiado:** a tabela herdada da
  fundação não indexa a FK que a agregação da T32 vai filtrar. No volume do MVP
  não há impacto mensurável e alterar o schema exigiria uma nova migração
  Alembic fora do escopo desta task; o índice fica registrado para quando a T32
  medir agregações por período em base maior.

## 4. O que vem a seguir (Roadmap Imediato)

- **T23 (UI de feedback):** vai consumir este endpoint com os botões
  aceitar/descartar via HTMX e exibir as fontes da `Recommendation`; como o
  corpo já é `form`-encoded, não precisa de camada de adaptação. A UI deve
  desabilitar/realçar a decisão vigente para reduzir cliques repetidos.
- **T32 (Dashboard de KPIs):** agrega adoção e aceitação por tenant e período
  reutilizando `list_by_recommendation`; deve contar **a última decisão por
  recomendação** (e não o total de linhas) para não somar trocas de decisão. A
  filtragem por tenant vem da junção com `Recommendation`/`Conversation`, já que
  `Feedback` não carrega `empresa_id`.
- **T33 (aceitação P1):** o fluxo ponta a ponta (recomendar → aceitar →
  recarregar e ver o registro) fecha COP-06 junto com o histórico da T20.

## 5. Validação de Qualidade e Segurança

- **Garantias de negócio e privacidade:** a decisão é sempre gravada com
  `usuario.id` da sessão e só depois de a recomendação ser autorizada contra
  `empresa.id` **e** `usuario.id`; nenhum id de tenant/usuário vem do cliente.
  Testes de integração provam isolamento entre empresas (empresa B → 404) e
  entre usuários da mesma empresa (colega → 404), sem linha de feedback criada.
  Não há chamada a LLM nem envio de dado a provedor externo nesta task.
- **Cobertura e testes automatizados:** `tests/web/test_feedback.py` cobre 401
  sem sessão, aceite + descarte persistidos em ordem com o usuário atuante,
  isolamento entre tenants, isolamento entre usuários do mesmo tenant e decisão
  inválida → 422 (5 testes de integração). Execução focada: **5 passed**. Gate
  completo: **152 passed**, cobertura **97,73%** (gate de 80%), com
  `web/feedback.py` em **100%** e `repositories/conversations.py` coberto.
- **Padrões de qualidade:** `uv run python -m black --check src/ tests/` → 74
  arquivos inalterados; `uv run python -m ruff check src/ tests/` → All checks
  passed. Docstrings e nomes em português (`decisao`, `recomendacao`,
  `registrar_feedback`), `from __future__ import annotations` presente, nenhum
  comentário fora de docstring, nenhum `print` e funções bem abaixo de 50 linhas.

## Achados corrigidos no self-review

- **Contrato de escopo implícito no `FeedbackRepository` (média):** como
  `Feedback` não tem `empresa_id`, era fácil um consumidor futuro (T32) ler
  decisões sem autorizar a recomendação. O docstring da classe agora declara que
  a autorização prévia via `RecommendationRepository.get_do_usuario` é
  obrigatória, espelhando o que `MessageRepository` já documentava.
- **Semântica *append-only* não documentada (média):** `add_feedback` não
  deixava claro que cada clique insere nova linha (sem `upsert`), o que poderia
  levar a T32 a contar linhas em vez da decisão vigente. Os docstrings de
  `add_feedback` e `list_by_recommendation` passaram a registrar a regra "última
  linha vence".
- **404 da rota sem justificativa escrita (baixa):** o docstring de
  `registrar_feedback` agora explica que o 404 é intencional para não revelar
  existência de recursos de outros tenants, e que o corpo em `form` atende ao
  HTMX da T23.
- **Sem achados** de lint, formatação, tipagem, injeção, vazamento de segredo ou
  quebra de tenancy além dos acima.
