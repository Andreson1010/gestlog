# ADR: t21-recomendacao-fontes-insuficiencia

## 1. Contexto & Objetivo

A T17 deu ao copiloto um serviço que injeta o tenant nas tools e roda o grafo
supervisor + especialistas; a T18 transmitiu a resposta por SSE; a T19 desenhou a
tela; a T20 passou a guardar o histórico; e a T34 já expunha uma tool comum,
`enviar_resposta_logistica`, para os três especialistas fecharem a resposta de
forma padronizada. Faltava o que dá sentido a tudo isso: a resposta chegar ao
operador como **recomendação explicada** — texto, justificativa e as fontes do
dado usado — e a recusa honesta quando não há base. É o critério **COP-04** do
épico P1: *AC1 "apresentar recomendação + justificativa + a(s) fonte(s)"* e
*AC2 "informar a insuficiência, sem recomendação inventada"*. Sem isso, a T22
(feedback) não teria o que aceitar/descartar, nem a T23 (UI) o que exibir.

O desafio arquitetural central não é decidir o que é uma boa recomendação: é
**extrair estrutura de um diálogo multiagente em texto livre sem gastar uma
segunda chamada ao LLM**. O grafo devolve `AIMessage`s; o modelo é quem sabe a
justificativa e as fontes. Inventar um segundo passo de "extração estruturada"
dobraria latência e custo por pergunta — e, pior, reintroduziria o risco de
alucinação exatamente no ponto que deveria ancorar a confiança. A decisão
aprovada foi usar a própria tool comum como **passo terminal** do especialista: o
modelo declara resposta, justificativa e fontes num schema de function calling, e
o sistema lê isso como formato próprio, não como texto adivinhado.

## 2. Decisões de Arquitetura

**1. A tool comum vira passo terminal detectado por `create_specialist_node`**

Antes, o nó ReAct executava qualquer tool e continuava o loop. Agora
`create_specialist_node` inspeciona `response.tool_calls`: se houver uma chamada a
`enviar_resposta_logistica` **e ela for a única chamada daquele passo**, ele
**executa essa tool, devolve o texto composto como `AIMessage` final e encerra o
turno**, sem mais passos. A guarda de "única chamada" (achado do code review,
`tests/agents/test_specialists.py::test_specialist_nao_encerra_com_tool_comum_em_lote`)
impede que um modelo que agrupe a tool comum com uma tool de domínio no mesmo
passo encerre a resposta sem ter consultado o dado — nesse caso o passo vira um
passo normal e o ciclo continua. A justificativa
prática é direta: o operador ganha uma resposta cujo formato já traz as fontes no
corpo (`Resposta logística: … / Justificativa: … / Fontes: …`), e o produto colhe
uma declaração estruturada do próprio modelo, no mesmo passe que gerou o texto.
Um segundo passo de extração criaria mais uma oportunidade de errar o motivo, e o
schema derivado pelo `@tool` já obriga `resposta` e dá `default: ""` a
`fontes`/`justificativa`, então o LLM **escolhe** declarar (ou não) a base — o que
torna a ausência de fonte um sinal confiável, não um parsing frágil.

**2. `dominio` entra no `AgentState`, e o nó devolve `SpecialistOutput`**

O serviço precisa saber **qual especialista** encerrou a recomendação para
gravar `Recommendation.dominio`; só o nó sabe disso. Em vez de inferir o domínio do
texto (o que exigiria ler `state["next"]` a cada volta e quebraria quando o
supervisor muda de especialista no meio), o nó devolve `{"messages": [...],
"dominio": name}` e a `state.py` ganha `dominio: NotRequired[str]`. O retorno
deixou de ser `dict[str, Any]` e passou a um `TypedDict` `SpecialistOutput`
(`messages` + `dominio`), preservando a intenção do campo para quem ler o código.
Como o grafo é stateless por pergunta (`run_query` cria o estado do zero a cada
turno), não há vazamento de domínio entre perguntas; e o `dominio` só é usado
quando a resposta final tem base — no caminho de insuficiência ele é descartado.

**3. `Recomendacao` como dataclass imutável e o parser do formato próprio**

O serviço expõe `Recomendacao(dominio, texto, justificativa, fontes,
insuficiente)` (dataclass `frozen`) e `extrair_recomendacao`, que quebra o texto
composto por rótulos **exportados de `tools/common.py`**
(`ROTULO_RESPOSTA/ROTULO_JUSTIFICATIVA/ROTULO_FONTES`) — não por strings
mágicas duplicadas. A separação usa `rsplit` no *último* marcador de cada rótulo
e depois converte `fontes` ("estoque, TMS") em `tuple[str, ...]` com split por
vírgula/ponto e vírgula. O ponto crítico de robustez: como `rsplit` pega a última
ocorrência, um "Fontes:" que o próprio LLM escreva no corpo da resposta não
desloca a linha real de fontes que a tool acrescenta ao final — comportamento
verificado à mão. Compartilhar os rótulos entre a tool que **escreve** e o
serviço que **lê** é o que impede o formato de divergir silenciosamente.

**4. Sem fonte ⇒ insuficiência; e só com base se persiste `Recommendation`**

`extrair_recomendacao` marca `insuficiente=True` quando o texto está vazio ou
quando `fontes` está vazia, e nesse caso devolve a constante
`MENSAGEM_INSUFICIENCIA` em vez do texto do modelo. `registrar_turno` grava
sempre pergunta e resposta, mas **só** chama
`RecommendationRepository.add_recommendation` quando
`recomendacao.insuficiente` é falso. A lógica é de negócio, não de estilo: a F1 é
read-only sobre os dados do tenant (AD-001), então uma recomendação sem fonte
citável é, por definição, não ancorada; recusar é a única saída compatível com
*"sem recomendação inventada"*. Persistir a `Recommendation` apenas quando há
base mantém a T22 limpa: os botões aceitar/descartar existirão somente sobre
recomendações reais.

**5. `justificativa` entra na tool como terceiro parâmetro opcional**

A assinatura de `enviar_resposta_logistica` passou de
`(resposta, fontes="")` para `(resposta, fontes="", justificativa="")`. Foi uma
extensão **retrocompatível** do contrato da T34: o novo argumento é opcional, o
schema anterior continua válido e todos os testes da T34 seguem passando sem
edição. Colocar a justificativa na tool — e não tentar derivá-la no serviço — é a
consequência natural da decisão 1: o LLM é o único que sabe *por que* recomenda, e
o schema é o canal legítimo para essa declaração. O texto só renderiza a linha
`Justificativa:` quando ela vem preenchida, de modo que respostas antigas sem
motivo não ganham rótulo órfão.

## 3. Concessões e Escolhas Práticas (Trade-offs)

- **Parsear o nosso próprio texto composto:** o formato é escrito pela tool e
  lido pelo serviço, então o parser é determinístico hoje; contudo, ele é
  acoplado à ordem dos rótulos. A mitigação é os rótulos morarem em
  `tools/common.py` e haver teste de ida e volta
  (`test_extrair_recomendacao_estrutura_texto_justificativa_e_fontes`). A
  alternativa "certa" seria um canal estruturado (Pydantic/tool args) direto no
  estado, mas isso exigiria mexer no contrato de mensagens do LangGraph e foi
  conscientemente adiado.
- **Fontes vazias ⇒ insuficiência (e a pergunta de esclarecimento):** o
  prompt do transporte manda *perguntar* quando falta origem/destino/peso
  (COP-02 AC3). Como o especialista agora encerra sempre pela tool, uma pergunta
  de esclarecimento sem fonte cai na regra acima e é substituída pela
  `MENSAGEM_INSUFICIENCIA` genérica — ou seja, perde-se a pergunta específica.
  É o preço, aceito nesta task, de não exibir como "recomendada" uma resposta sem
  base. Refinar a distinção "sem base" × "preciso de um dado do usuário" fica
  para a T25/T29, quando houver avaliação e redação de PII no caminho.
- **`answer()` devolve o texto composto (com rótulos) no caminho feliz:** o
  *Done when* pede que "a resposta traga fontes", então na F1 a tela exibe
  `Fontes: …` em texto puro; a forma limpa (`recomendacao.texto`) é o que se
  persiste em `Recommendation.texto`. Formatar a apresentação (e parar de mostrar
  os rótulos crus) é escopo da T23.
- **`dominio` é *last-writer-wins* no estado compartilhado:** sem reducer, um
  especialista posterior sobrescreve o anterior. É seguro porque somente o nó
  terminal grava o campo e o serviço só o consome quando a resposta final tem
  fonte; ainda assim, se um especialista "alucinasse" um `Fontes:` no corpo sem a
  tool, o domínio herdado seria o do último especialista. Cenário improvável e
  não persistível (a resposta viraria suficiente só com esse texto), registrado.
- **`_SEPARADORES_FONTES = (";", ",")`:** um nome de fonte que contenha vírgula
  é dividido em duas. Aceitável para o contrato textual do MVP; a T23/T29 podem
  reforçar o formato.
- **`justificativa` alarga o schema da tool da T34:** a ADR da T34 registrou a
  assinatura de dois parâmetros; este documento a supersede de forma explícita.
  Como o parâmetro é opcional, nenhum consumidor quebra — a evolução é aditiva.

## 4. O que vem a seguir (Roadmap Imediato)

- **T22 (Feedback aceitar/descartar):** agora existe uma `Recommendation`
  persistida por conversa; o endpoint de feedback pode apontar para o id real da
  recomendação (não para a mensagem de texto), com usuário, tenant e timestamp.
- **T23 (UI de feedback):** os botões aceitar/descartar e a exibição das fontes
  passam a consumir a `Recommendation` estruturada, em vez de depender do corpo
  composto que a F1 mostra cru.
- **T25/T29 (PII e golden set):** a redação de PII incide sobre a pergunta/resposta
  persistidas; o golden set passa a medir "fonte correta" e alucinação — é o lugar
  natural para decidir se a pergunta de esclarecimento (COP-02 AC3) merece um
  caminho próprio, separado da insuficiência sem base.
- **T24/T26/T27:** redação de PII, auditoria/retenção e medição de uso pousam em
  cima da conversa e da recomendação que esta task estruturou.

## 5. Validação de Qualidade e Segurança

- **Garantias de negócio e privacidade:** a recomendação é gravada por
  `RecommendationRepository`, sempre presa a uma `Conversation` cujo
  `(empresa_id, user_id)` vêm da sessão autenticada — nenhum id vem do cliente, e
  a leitura continua escopada por tenant (herdada da T20). A insuficiência **não**
  é persistida como recomendação, evitando alimentar aceite/descarte e métricas
  com algo que não foi de fato recomendado. Nenhum dado sai para provedor externo
  nesta task e a API do LLM não é chamada nos testes (modelo fake).
- **Cobertura e testes automatizados:** a task adiciona/ajusta testes em
  `tests/copilot/test_service.py` (estruturação, insuficiência por fontes vazias,
  insuficiência sem tool comum, fora de escopo preservado, persistência da
  `Recommendation` e não-persistência na insuficiência), `tests/agents/test_specialists.py`
  (nó encerra com a tool comum e devolve `dominio`), `tests/test_tools.py`
  (justificativa renderizada) e nos testes web de SSE/UI. Execução focada: **55
  passed**. Gate completo: **146 passed**, cobertura **97,67%** (gate de 80%),
  com `copilot/service.py`, `tools/common.py`, `repositories/conversations.py` e
  `state.py` em **100%**.
- **Padrões de qualidade:** `black --check src/ tests/` → 72 arquivos
  inalterados; `ruff check src/ tests/` → All checks passed. Docstrings e nomes
  de código em português (`recomendacao`, `justificativa`, `fontes`,
  `insuficiente`), nenhum comentário fora de docstring e nenhum `print`.

## Achados corrigidos no self-review

- **Duplicação do nome da tool terminal (baixa):** `agents/base.py` repetia a
  string `"enviar_resposta_logistica"` num `_TERMINAL_TOOL`, enquanto a tool real
  vivia em `tools/common.py` — renomear a função quebraria a detecção em
  silêncio. Agora `tools/common.py` expõe `NOME_TOOL_RESPOSTA =
  enviar_resposta_logistica.name` e `base.py` importa essa constante; há um único
  dono do nome.
- **Tipo de retorno alargado para `dict[str, Any]` (baixa):** a assinatura
  `SpecialistNode` havia perdido toda a informação sobre o que o nó devolve.
  Substituída pelo `TypedDict` `SpecialistOutput` (`messages` + `dominio`), que
  documenta o contrato sem `Any`.
- **Sem achados** de lint, formatação, tenancy ou segurança além do acima.
