# ADR: t25-integrar-pii

## 1. Contexto & Objetivo

A F1 assumiu um compromisso explícito de LGPD (AD-005): dado pessoal de clientes
— destinatários, endereços e telefones de contato — não pode sair no prompt do
LLM. A T24 entregou a peça isolada que reconhece e minimiza essa PII
(`redact(texto) -> RedactedText`, em `src/gestlog/privacy/`), mas enquanto ela não
estivesse **ligada** ao caminho real da pergunta, a garantia valia só no papel: o
copiloto continuava mandando o texto cru do operador ao provedor e guardando esse
mesmo texto no histórico. A T25 fecha essa lacuna e cumpre dois critérios do
épico — **SEC-01** (*"redigir/minimizar a PII antes do envio ao LLM"*) e **SEC-03**
(*"o que fica retido no histórico também é minimizado"*).

A pergunta de projeto aqui não é "como detectar PII" (isso é a T24), mas **onde a
redação entra e qual versão do texto circula e é retida**. A decisão de produto já
estava tomada e é o eixo desta task: a pergunta redigida é, ao mesmo tempo, **o que
vai ao LLM** e **o que é persistido** em `Message.conteudo_redigido`; o original não
é enviado nem armazenado. A tela ao vivo continua mostrando o que o operador
digitou, porque isso é dado dele, exibido no navegador dele, sem passar pelo
provedor. O desafio prático é encaixar essa política no único ponto de entrada do
copiloto — `CopilotService.answer` — sem duplicar chamadas, sem tocar no contrato
de mensagens do grafo e sem depender de rede no teste que prova o *Done when*.

## 2. Decisões de Arquitetura

**1. Um único ponto de passagem: redigir em `answer`, antes de montar o grafo**

`CopilotService.answer` passou a chamar `redact(pergunta)` como primeira operação e
a usar `redacao.texto` tanto em `run_query(grafo, redacao.texto, ...)` quanto em
`registrar_turno(..., redacao.texto, ...)`. Concentrar a redação nesse funil é
deliberado: o serviço é o gargalo por onde toda pergunta passa (a rota SSE
`/chat/stream` e qualquer consumidor futuro chamam `answer`), então não existe
caminho alternativo em que o texto original chegue ao modelo. A alternativa —
redigir dentro do grafo ou de cada especialista — espalharia a responsabilidade por
vários nós, multiplicaria os lugares onde um novo nó poderia "esquecer" a redação e
ainda criaria a chance de o histórico ser gravado antes do filtro. Fazer a chamada
uma única vez, no início, também significa **zero latência adicional perceptível**:
`redact` é uma função pura de regex, sem I/O e sem rede, executada antes de o
provedor ser acionado. Em termos de fronteiras, `copilot/` pertence à fatia `apps`
e `privacy/` à fundação `libs` (registrado em `docs/specs/project/STATE.md`), então
`apps → libs` é a direção permitida e o import de `gestlog.privacy.redact` não
inverte nada.

**2. A versão minimizada é a única que existe depois do serviço**

Não há campo para o original na `Message`: o repositório grava apenas
`conteudo_redigido`, e o serviço passa `redacao.texto` para
`registrar_turno`. A intenção de privacidade é objetiva: minimização de dados
(*data minimization*), isto é, reter o mínimo possível, e não uma cópia sensível
"para consulta". Isso também resolve uma inconsistência latente de nomenclatura —
o campo sempre se chamou `conteudo_redigido`, mas até aqui recebia texto literal; a
partir desta task o nome volta a descrever a realidade, em linha com a ADR da T20
("a redação de PII passa a agir sobre o conteudo_redigido"). A persistência
continua presa à `Conversation` da sessão autenticada,
`(empresa_id, user_id)` vindos do tenant, herdada da T20/T21; a mudança é apenas
*qual texto* é gravado, nunca *para quem*.

**3. O original fica na camada de apresentação, fora do servidor de IA**

A UI ao vivo preserva a experiência atual: o formulário do chat dispara
`GET /chat/pergunta?pergunta=...` e o fragmento `chat_turno.html` ecoa esse texto
via query param; a assinatura SSE `/chat/stream` recebe a mesma string e a entrega
a `answer`, que redige antes de qualquer chamada ao modelo. Ou seja, o original
existe **dentro do processo e no navegador do próprio operador**, mas não é
enviado ao provedor nem persistido. Essa separação é o que permite atender
simultaneamente à usabilidade (o operador reconhece o que digitou na hora) e à
LGPD (nada de PII fica retido no backend depois do turno). Quando o histórico é
recarregado, a intenção é mostrar a versão minimizada — comportamento coerente com
a minimização e registrado como trade-off abaixo.

**4. O teste de *Done when* observa o que o modelo recebeu, não o banco**

O critério de aceite é "o prompt enviado ao LLM não contém a PII de entrada", então
o teste precisa olhar **a mensagem que chegou ao modelo**, e não apenas conferir o
registro persistido (que poderia estar redigido enquanto o grafo mandou o original —
justamente o bug que a task existe para impedir). Para isso, o `FakeChatModel` de
`tests/conftest.py` ganhou `mensagens_recebidas`, populado nos dois pontos de
entrada do modelo: no `invoke` dos especialistas e no `invoke` do `_Router` de
`with_structured_output` do supervisor. O teste
`test_answer_redige_pii_antes_do_llm` roda uma pergunta com nome e telefone
(`"Falar com João Silva no (11) 98765-4321..."`), concatena tudo o que o fake
recebeu e afirma a **ausência** de `"João"`, `"Silva"` e `"98765"`, bem como a
presença dos marcadores `[NOME]` e `[TELEFONE]`. Como o fake é um duplo completo e
não há rede/Ollama na suíte, a asserção é determinística e barata. Os testes
`test_answer_persiste_pergunta_redigida` e `test_answer_sem_pii_preserva_pergunta`
cobrem a segunda metade do critério — a retenção minimizada — e a não-regressão
para texto sem PII.

**5. O fake não mudou de contrato; só ganhou um espião passivo**

`mensagens_recebidas` é um buffer de leitura: as filas `routes`, `tool_calls` e
`final` e o comportamento de `bind_tools` continuam idênticos, de modo que os
testes de copiloto, agentes e grafo seguem passando sem edição. A captura é
tipada como `list[list[BaseMessage]]` para documentar o formato real (listas de
mensagens por chamada), e o helper de teste converte **todo** conteúdo para texto —
inclusive blocos estruturados — para que nenhuma PII possa escapar da asserção por
estar em um tipo de conteúdo que o filtro antigo ignorava. É um detalhe pequeno,
mas num teste de segurança o pior resultado não é falhar: é passar por engano.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **O histórico passa a exibir marcadores no lugar da PII.** É a consequência
  direta e aceita da minimização: ao reabrir a conversa, o operador vê
  `[NOME]`/`[TELEFONE]` em vez do nome e do número originais. A perda de
  fidelidade visual é o preço de não reter o dado sensível no backend; para o
  MVP, em que o histórico serve de contexto e auditoria de decisão (e não de
  transcrição literal), isso é seguro. Guardar separadamente o original só para
  reexibição reabriria exatamente o risco que SEC-03 manda fechar.
* **A redação é heurística, não NER.** A T25 apenas aplica o contrato da T24; os
  falsos negativos estruturais (nomes fora da allowlist, endereço sem número,
  telefone colidente com número de negócio) continuam valendo e agora têm impacto
  real no caminho do LLM. O erro é enviesado para o lado seguro (redigir demais),
  e a evolução é a allowlist por tenant e/ou NER local como complemento — decisão
  de outra iteração, com teste e política antes de virar default.
* **Uma redação, dois usos — sem canal separado.** LLM e histórico consomem o
  mesmo `redacao.texto`. Isso é intencional e evita divergência (gravar uma versão
  e enviar outra), mas impede, por construção, que o histórico preserve detalhe
  que o modelo não viu. Como a decisão de produto já fixou esse comportamento, a
  simplicidade do fluxo único vence a flexibilidade de dois textos.
* **`redact` roda no caminho crítico, mas é pura.** Trocar por um serviço de PII
  externo ou por NER adicionaria latência, dependência e — no caso de serviço
  remoto — *mais* um destino para o dado sensível. Regex determinística é o
  mínimo viável que protege o caso real sem custo por token.
* **Sem resolução de política por tenant nesta task.** O módulo aceita
  `PoliticaRedacao`, mas `answer` usa `POLITICA_PADRAO`. Resolver a política da
  empresa logada exige um repositório/atributo que ainda não existe; aplicar o
  mecanismo com o default é o passo seguro, e o gancho já está pronto para a
  iteração que introduzir a configuração por tenant.

## 4. O que vem a seguir (Roadmap Imediato)

* **T26 (Auditoria e retenção):** o serviço já tem `RedactedText.categorias` em
  mãos; a trilha pode registrar "houve redação de nome/telefone/endereço" **sem**
  persistir o valor sensível, fechando SEC-01 AC3 e dando à operação visibilidade
  de quanta PII o copiloto recebe.
* **T27 (Medição de uso):** os contadores de tokens/uso passam a incidir sobre a
  pergunta já redigida, alinhando custo medido com o texto realmente enviado.
* **T29/T32 (Golden set e KPIs):** a redação incide sobre as perguntas do conjunto
  de avaliação; é onde se mede se a minimização degradou a qualidade da
  recomendação e se os falsos negativos da allowlist importam na prática.
* **Configuração por tenant:** resolver a `PoliticaRedacao` da empresa a partir da
  sessão, permitindo allowlists específicas (transportadoras, razões sociais) sem
  alterar o default de outro tenant.
* **Evolução da heurística:** endurecer endereço sem número, mitigar a colisão de
  telefone com números de negócio e estudar NER local como complemento — cada item
  com teste e política antes de virar padrão.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio e privacidade:** a pergunta original não é enviada ao
  provedor nem gravada — `answer` só conhece `redacao.texto` depois do filtro. A
  prova é comportamental e direta: `test_answer_redige_pii_antes_do_llm` inspeciona
  todas as mensagens que o `FakeChatModel` recebeu (supervisor e especialistas) e
  afirma ausência de nome e telefone, enquanto
  `test_answer_persiste_pergunta_redigida` confirma a mesma minimização no
  `Message.conteudo_redigido`. A persistência segue escopada por
  `(empresa_id, user_id)` da sessão autenticada, sem id vindo do cliente. Nenhuma
  chamada de rede é feita nos testes.
* **Cobertura e testes automatizados:** `tests/copilot/test_service.py` cobre os
  três cenários novos (redação antes do LLM, persistência redigida e texto sem PII
  intacto). Execução focada `tests/copilot tests/privacy`:
  **39 passed**; `tests/copilot tests/privacy tests/agents tests/test_graph.py`
  (contrato do fake): **51 passed**. Gate completo: **177 passed**, cobertura
  **97,84%** (gate de 80%), sem alteração no total de testes — a task reforça
  asserções, não amplia superfície.
* **Padrões de qualidade:** `uv run python -m black --check src/ tests/` → 78
  arquivos inalterados; `uv run python -m ruff check src/ tests/` → All checks
  passed. `from __future__ import annotations` presente nos três arquivos, sem
  comentários fora de docstring, sem `print`, funções abaixo do limite de 50
  linhas, docstrings e nomes em português e imports na direção `apps → libs`.

## Achados corrigidos no self-review

* **Tipo do buffer do fake era `list[Any]` (baixa, clareza de contrato):** o novo
  `mensagens_recebidas` e os parâmetros `messages` de `invoke` e do `_Router`
  estavam sem informação de tipo. Passaram a `list[list[BaseMessage]]` e
  `list[BaseMessage]`, documentando que cada chamada recebe uma lista de mensagens
  LangChain — o contrato que o teste de PII depende de inspecionar.
* **O helper de teste podia mascarar PII (média, robustez da asserção de
  segurança):** `_texto_recebido` filtrava `isinstance(content, str)` e descartava
  silenciosamente conteúdo não textual. Se uma mensagem futura trouxesse PII em
  bloco estruturado, a asserção de *Done when* passaria mesmo com o dado vazando.
  O helper agora converte **todo** conteúdo para texto via
  `str(getattr(mensagem, "content", mensagem))`, sem filtro que possa esconder uma
  ocorrência, e teve a docstring atualizada.
* **Sem achados** de lint, formatação, tenancy, fronteiras de camada ou segurança
  além dos acima; nenhuma correção exigiu mudança de comportamento em produção.
