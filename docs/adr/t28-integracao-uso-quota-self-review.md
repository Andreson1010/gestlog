# ADR: t28-integracao-uso-quota

## 1. Contexto & Objetivo

A T27 entregou o módulo de medição (`record_usage`) e o bloqueio por quota
(`check_quota`) prontos, mas ainda desconectados do produto: o copiloto continuava
respondendo sem nunca registrar o consumo nem consultar o teto mensal. O requisito
**QUA-02** só se torna real quando a regra passa a valer no caminho de verdade — é
a T28 que liga o medidor ao `CopilotService.answer`, garantindo duas promessas de
negócio: *toda* resposta conferida pelo LLM tem seu custo atribuído à empresa, e
uma empresa que estourou a quota recebe uma mensagem clara em vez de uma resposta
cara e, pior, uma sessão derrubada por exceção.

O desafio arquitetural não é chamar duas funções: é descobrir **onde** o consumo
pode ser contado sem se perder. O nó especialista do grafo foi desenhado na T21
para devolver apenas a resposta final, descartando as mensagens intermediárias
(inclusive as trocas de ferramenta) que carregam `usage_metadata`. Somar tokens
relendo `state["messages"]` no serviço perderia essas chamadas silenciosamente —
um buraco na medição que faria a quota liberar mais do que o contratado. A solução
precisou, portanto, viajar junto do estado do grafo, não da conversa.

## 2. Decisões de Arquitetura

**1. O acumulador de tokens vive no `AgentState`, porque é o único lugar que vê
todas as chamadas**

`AgentState` ganhou `tokens_usados: NotRequired[Annotated[int, operator.add]]`.
O `Annotated[..., operator.add]` registra um *reducer*: cada atualização de um nó
é somada ao valor corrente em vez de sobrescrevê-lo. Isso é exatamente o
comportamento necessário quando o supervisor encadeia mais de um especialista na
mesma consulta — cada um devolve o seu consumo e o canal acumula o total. Em
`create_specialist_node`, o helper `_tokens_da_resposta(response)` extrai
`usage_metadata["total_tokens"]` de cada `model_with_tools.invoke` (inclusive os
passos intermediários que contêm tool calls, que de outra forma escapariam), e o
valor é devolvido em **todos** os caminhos de saída do nó: resposta final, passo
terminal da tool comum e estouro de `max_steps`. Deixar um caminho sem
`tokens_usados` abriria a mesma fenda que motivou o desenho; o `SpecialistOutput`
declara a chave para o contrato ficar explícito. O reducer também é robusto à
ausência do campo: quando nenhum especialista roda (rota direta para `FINISH`), o
canal resolve para `0`, e o serviço lê `estado.get("tokens_usados", 0)` sem risco
de `None`.

**2. O bloqueio é pré-chamada e vira mensagem de domínio, sem exceção vazando**

`answer` chama `check_quota(self.session, self.empresa_id, resolvido)` antes de
redigir a pergunta e antes de tocar o grafo. Ao capturar `QuotaExcedida`, devolve
`MENSAGEM_QUOTA_EXCEDIDA` — texto em português que explica o teto mensal e orienta
a procurar o administrador — e retorna imediatamente. Nenhuma exceção sobe para a
rota HTTP: bloquear por quota é um estado de negócio esperado, não uma falha de
infraestrutura, e a *Done when* exige que a quota "bloqueie sem derrubar a sessão".
Como o retorno acontece antes de qualquer `redact`, `build_graph` ou `run_query`,
o modelo não é chamado (custo evitado de verdade, que é o ponto do pré-call) e
nenhum turno ou uso é gravado. A mensagem foi reexportada em
`copilot/__init__.py` para que a borda web a reconheça sem importar detalhes
internos.

**3. O consumo entra na mesma unidade de trabalho do turno**

Depois que o grafo responde, o serviço chama `record_usage(...,
int(estado.get("tokens_usados", 0)))` **antes** de `registrar_turno`. A ordem e a
ausência de `commit` em `record_usage` são deliberadas: ambos escrevem na mesma
sessão e o `commit()` único de `registrar_turno` fecha turno, recomendação,
auditoria e consumo de uma vez. Assim não existe estado em que a empresa pagou por
uma resposta que não ficou no histórico, nem telemetria de um turno que falhou —
o mesmo padrão transacional que a T26 fixou para a auditoria. O modelo registrado
vem de `resolvido.llm_model`, sem string mágica no serviço.

**4. A quota consultada é a mensal da T27, por empresa**

O serviço não recria política de janela nem de limite: apenas aciona
`check_quota`, que soma o mês corrente por `empresa_id` e compara com
`Settings.llm_monthly_token_quota` (comportamento conservador `usado >= quota`).
Reaproveitar a regra já testada mantém uma única fonte de verdade para "quanto a
empresa já gastou" e garante que a leitura no caminho do copiloto seja a mesma que
a T30 usará nos KPIs.

**5. Isolamento por empresa atravessa toda a ligação**

`check_quota` e `record_usage` sempre recebem `self.empresa_id`; a telemetria
gravada nunca cruza tenants. O teste `test_answer_bloqueia_quota_sem_chamar_llm`
usa uma empresa com consumo e verifica que o bloqueio é local, sem afetar nem
inventar uso.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **Tokens do supervisor ficam fora da conta (best-effort).** O supervisor roteia
  via `with_structured_output`, e a T28 não instrumenta esse caminho para não
  alterar a arquitetura de roteamento. O consumo registrado cobre as chamadas dos
  especialistas, que são a maior parte do custo; o roteamento consome pouco e entra
  como débito. É uma subcontagem conhecida, não um vazamento de quota.
* **A contagem de tokens depende do provedor reportar `usage_metadata`.** Quando o
  modelo não devolve o metadado, `_tokens_da_resposta` retorna `0` e o turno é
  registrado com zero. Preferimos registrar um turno com consumo não medido a
  falhar a resposta do usuário; a T27 já assume que o bloqueio é best-effort e a
  medição é aproximada.
* **O bloqueio só é checado no início da chamada.** Duas requisições simultâneas
  podem ler o mesmo uso e ambas passarem, e uma chamada já autorizada pode
  ultrapassar levemente o teto. É a limitação herdada da T27 (freio, não fatura
  exata) e aceitável no volume do MVP.
* **O bloqueio não gera evento de auditoria de degradação.** A T27 idealizou um
  evento para bloqueios; a T28 mantém a mudança mínima e apenas devolve a
  mensagem. O catálogo da T26 está pronto para receber o evento quando o produto
  quiser medir quantos acessos são barrados por quota.

## 4. O que vem a seguir (Roadmap Imediato)

* **T29–T33 (golden set, avaliação, admin, KPIs, aceitação P1):** a telemetria
  agora alimentada permite que a T30 leia `UsageRepository.total_tokens` (all-time)
  e `total_tokens_desde` para relatórios de custo por empresa e período.
* **Medir o supervisor:** instrumentar `with_structured_output` para somar os
  tokens de roteamento ao `tokens_usados`, fechando a subcontagem conhecida sem
  mudar o contrato do grafo.
* **Evento de auditoria de bloqueio por quota:** registrar a degradação no
  catálogo da T26 para dar visibilidade operacional a quantos acessos são barrados.
* **Endurecimento da concorrência:** se o volume crescer, avaliar reserva de
  tokens ou contador atômico para tornar o bloqueio estrito.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio e privacidade:** `test_answer_registra_uso_do_mes` prova
  que o consumo do turno é atribuído à empresa e ao modelo configurado;
  `test_answer_soma_tokens_de_multiplos_especialistas` prova que o reducer soma o
  consumo de dois especialistas na mesma resposta (20 tokens) e grava um único
  registro; `test_answer_bloqueia_quota_sem_chamar_llm` prova que, ao estourar, o
  LLM não é chamado, o histórico permanece vazio, nenhum uso extra é gravado e a
  resposta é a mensagem clara de quota. Nenhum teste toca rede/Ollama — o modelo
  continua sendo o `FakeChatModel`, agora com `usage_metadata` configurável.
* **Cobertura e testes automatizados:** executado o gate completo,
  **198 passed**, cobertura **97,97%**, com `agents/base.py`, `copilot/service.py`,
  `copilot/metering.py` e `state.py` em **100%**. Suíte focada da task:
  `tests/copilot tests/agents tests/test_graph.py tests/audit` → **55 passed**.
* **Padrões de qualidade:** `uv run python -m black --check src/ tests/` → 84
  arquivos inalterados; `uv run python -m ruff check src/ tests/` → All checks
  passed. `from __future__ import annotations` presente, docstrings e nomes em
  português, sem comentários fora de docstring, sem `print`, funções abaixo de 50
  linhas e sem valor hardcoded (quota e modelo vêm de `Settings`). O reducer foi
  verificado empiricamente para soma entre múltiplos especialistas e para ausência
  do campo, sem regressão nos testes de grafo e agentes.

## Achados corrigidos no self-review

* **`_tokens_da_resposta` podia estourar com `total_tokens=None` (leve, robustez):**
  em `src/gestlog/agents/base.py`, `int(uso.get("total_tokens", 0))` falharia com
  `TypeError` se um provedor compatível devolvesse a chave presente e nula. Passou
  a `int(uso.get("total_tokens") or 0)`, que trata ausente, `None` e `0` da mesma
  forma. Sem impacto no caminho feliz.
* **Caminho de bloqueio não assertava ausência de uso persistido (leve, teste):**
  a *Done when* fala em medir/bloquear; o teste só checava ausência de LLM e de
  histórico. Adicionada a asserção de que a contagem de `UsageRecord` da empresa
  permanece 1 após o bloqueio, comprovando que o retorno precoce não grava consumo.
* **Soma entre múltiplos especialistas não tinha teste de regressão (leve, teste):**
  a precisão central da T28 (o reducer acumular em vez de sobrescrever) estava
  verificada apenas por leitura. Adicionado
  `test_answer_soma_tokens_de_multiplos_especialistas`, que roteia estoque →
  transporte e exige um único registro de 20 tokens.
* **Sem demais achados:** nenhuma falha lógica ou de segurança fundamental,
  nenhuma exceção vazando para a rota e nenhuma alteração de arquitetura
  necessária. Tokens do supervisor permanecem fora da conta por decisão explícita,
  documentada acima.
