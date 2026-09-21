# ADR: Supervisor Loop & Chat SSE Failure

## 1. Context & Goal

O chat local do copiloto (issue #39) travava em "Consultando…" por minutos.
Com `qwen2.5:7b` e as tools reais do tenant, o especialista de estoque não
encerrava o loop ReAct pela tool `enviar_resposta_logistica`, estourava
`max_tool_steps` e devolvia "Limite de ferramentas atingido."; o supervisor
reencaminhava para o **mesmo** especialista indefinidamente até
`recursion_limit` (25), resultando em `GraphRecursionError`. A rota SSE não
tratava essa exceção, então o cliente nunca recebia o evento de fim e a UI
permanecia presa.

O objetivo é duplo: (a) dar ao supervisor uma condição de parada determinística
que impeça o ciclo com o mesmo especialista **sem** quebrar o encadeamento
legítimo entre especialistas distintos (`estoque`→`transporte`→`FINISH`); e
(b) transformar falhas do grafo em uma resposta amigável no streaming, em vez
de um travamento silencioso.

## 2. Architectural Decisions

- **Decision 1 — Rastrear domínios visitados no estado compartilhado.**
  `AgentState` ganhou `especialistas_visitados: NotRequired[Annotated[list[SpecialistName], operator.add]]`.
  - **Justification:** detectar repetição exige memória do que já foi executado
    ao longo dos saltos supervisor→especialista, e o estado do LangGraph é o
    único canal compartilhado entre os nós. O reducer `operator.add` acumula os
    registros entre passos (o primeiro update parte da lista vazia do canal), e
    o `NotRequired` preserva a compatibilidade: `run_query` continua invocando o
    grafo apenas com `messages`. Cada nó especialista passou a devolver
    `especialistas_visitados: [name]` nos **três** caminhos de retorno (resposta
    textual, tool comum e limite de passos), garantindo que todo especialista
    executado seja sempre registrado.

- **Decision 2 — Guarda de repetição no supervisor, decidida após consultar o modelo.**
  O nó do supervisor continua invocando o `with_structured_output(RouteDecision)`
  e só então aplica: `if route in visitados: route = "FINISH"`.
  - **Justification:** a rota só é conhecida depois da chamada ao modelo, então a
    consulta é inevitável. Bloquear **apenas a repetição** modela o requisito
    real e preserva o encadeamento de especialistas distintos. Uma primeira
    tentativa que forçava `FINISH` sempre que a última mensagem era `AIMessage`
    truncou o fluxo e quebrou 5 testes (soma de tokens de múltiplos
    especialistas e o golden set) — evidência registrada na lição L-006.

- **Decision 3 — Tratar a falha do grafo na fronteira SSE, com mensagem amigável.**
  `web/chat.py` envolve `servico.answer()` em `try/except Exception`, registra
  `logger.exception(...)` e transmite `MENSAGEM_ERRO_COPILOTO` + evento `fim`.
  - **Justification:** `CopilotService.answer()` roda o grafo inteiro de forma
    síncrona antes de o `StreamingResponse` começar; qualquer exceção abortava a
    requisição sem corpo. A rota HTTP é a fronteira correta para traduzir uma
    falha interna em contrato de transporte. O `except Exception` **não** captura
    `KeyboardInterrupt`/`SystemExit` (derivam de `BaseException`), e o log usa o
    logger do módulo, sem incluir a pergunta (evita vazar PII).

- **Decision 4 — Reexportar a nova constante pelo pacote `copilot`.**
  `MENSAGEM_ERRO_COPILOTO` foi adicionada ao `__init__.py` e ao `__all__`, e
  `web/chat.py` passou a importá-la de `gestlog.copilot`.
  - **Justification:** as demais mensagens (`MENSAGEM_FORA_DE_ESCOPO`,
    `MENSAGEM_INSUFICIENCIA`, `MENSAGEM_QUOTA_EXCEDIDA`) já seguiam esse padrão;
    manter a nova constante fora dele introduziria inconsistência de API.

## 3. Trade-offs & Compromises

- **Uma revisita legítima ao mesmo especialista na mesma pergunta deixa de ser
  possível.** Se o modelo quisesse voltar a `estoque` após passar por
  `transporte` para complementar a resposta, a guarda força `FINISH`. Aceitável
  pela spec: o requisito é impedir o ciclo; o encadeamento entre domínios
  **distintos** continua suportado (`estoque`→`transporte`→`FINISH` coberto por
  teste).
- **O supervisor paga uma chamada extra ao LLM para descobrir a repetição.** Não
  há como saber a rota sem invocar o modelo; uma chamada descartada é um custo
  muito menor que o loop de ~5 minutos com `GraphRecursionError`.
- **O `except Exception` amplo pode mascarar erros de programação** (ex.:
  `AttributeError`) como mensagem amigável. Mitigado por `logger.exception`, que
  preserva o traceback para diagnóstico; no limite de transporte, prioriza-se a
  resiliência do usuário sobre a propagação do erro.

## 4. Known Limitations

- A guarda depende de **todo** nó especialista registrar seu domínio. Um nó
  futuro que devolva `especialistas_visitados` ausente não seria detectado; o
  contrato é sustentado por `SpecialistOutput` e pelos testes de especialista.
- Com apenas 3 especialistas, o número de visitas é naturalmente limitado; o
  fluxo termina em poucos passos. Workflows que precisem revisitar domínios
  exigiriam outra estratégia de parada (ex.: contador por aresta ou flag de
  conclusão declarada pelo modelo).
- A guarda resolve o "não trava", mas **não** melhora a qualidade da resposta
  quando o especialista estoura `max_tool_steps`: o texto final vira
  insuficiência ("Não há dados suficientes..."). A causa de raiz — tool calling
  fraco do `qwen2.5:7b` — permanece e deve ser endereçada por escolha de modelo
  ou por tools de resposta mais dirigidas.
- A validação é feita com `FakeChatModel` (sem rede); o teste end-to-end com
  Ollama/`qwen2.5:7b` segue pendente de revalidação no harness local.
