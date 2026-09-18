# ADR: t27-uso-quota

## 1. Contexto & Objetivo

A tabela `usage_record` e o `UsageRepository` existem desde a T5, mas até aqui
nada alimentava o controle de consumo: o copiloto podia responder
indefinidamente, sem que ninguém soubesse quantos tokens cada empresa gastou, e
sem qualquer alavanca para conter custo. O requisito **QUA-02** pede exatamente
essa alavanca: registrar tokens/modelo por tenant e bloquear a chamada quando a
quota for excedida. Esta task entrega o **módulo de medição e quota**
(`src/gestlog/copilot/metering.py`) isolado; a ligação no caminho do copiloto é
deliberadamente a **T28**, para que a regra de negócio seja testável e revisável
antes de influenciar o comportamento do produto.

O desafio arquitetural não é somar inteiros: é definir *qual* consumo conta (só o
mês corrente, não o histórico all-time), *como* compará-lo a um limite sem
dispersar valores mágicos, e *onde* o bloqueio pode agir sem quebrar a
atomicidade do turno que a T26 acabou de consolidar. A quota precisa ser por
empresa — uma empresa não pode consumir a folga de outra — e precisa conversar
com a camada de dados sem violar a regra de que SQL só vive em
`repositories/` (AD-012).

## 2. Decisões de Arquitetura

**1. A janela é o mês corrente, não o consumo histórico — `uso_no_mes`**

`uso_no_mes(session, empresa_id, agora)` calcula o primeiro instante do mês com
`_inicio_do_mes(agora)` e delega a soma a
`UsageRepository.total_tokens_desde(empresa_id, desde)`. O `UsageRepository`
continua expondo `total_tokens` (soma all-time), mas a quota usa a janela mensal
porque é isso que o produto cobra e promete: um contratante que estourou o teto
em janeiro não pode ficar bloqueado para sempre, e `Settings.llm_monthly_token_quota`
é, como o nome diz, mensal. A soma all-time é mantida para telemetria/relatórios,
onde o histórico faz sentido. O corte é feito por `created_at >= início_do_mês`,
o que é indexável e determinístico.

**2. A quota é um bloqueio *pré-chamada*, explicitamente best-effort — `check_quota`**

`check_quota(session, empresa_id, settings, agora)` lê o uso do mês e levanta
`QuotaExcedida` **antes** de a chamada ao LLM acontecer. É o único ponto em que dá
para evitar custo de verdade: depois que o modelo respondeu, o token já foi
gasto. O limite vem de `Settings.llm_monthly_token_quota` — nenhum valor fica
hardcoded no módulo, então quem opera muda o teto por ambiente/`.env` sem tocar em
código. A condição de bloqueio é `usado >= quota`: a leitura conservadora de
"quota excedida" trata o teto como *teto de gasto*, não como *limite que ainda
tolera uma última unidade*. Como `check_quota` devolve o uso do mês quando há
folga, o chamador da T28 já tem a base para registrar a telemetria sem repetir a
consulta.

**3. `record_usage` registra, mas não confirma a transação — o gancho da T28**

`record_usage(session, empresa_id, modelo, tokens)` valida `tokens >= 0`,
adiciona o `UsageRecord` pelo repositório (que faz `flush`) e **não** chama
`commit`. A decisão é a mesma que a T26 fixou para a auditoria: o consumo entra na
**unidade de trabalho do turno**, e quem fecha a transação é o `registrar_turno`
do copiloto. Assim, ou o turno (pergunta, resposta, eventos) e o consumo entram
juntos, ou nenhum entra — não existe estado em que a empresa pagou por uma
resposta que não ficou registrada, nem telemetria de um turno que falhou. Repetir
o padrão de transação já provado reduz o risco da integração da T28 e mantém o
módulo sem opinião sobre *quando* confirmar.

**4. `QuotaExcedida` é um erro tipado, não uma string**

A exceção carrega `empresa_id`, `usado` e `quota` como atributos. Em T28 isso
permite que a borda HTTP transforme o bloqueio numa mensagem clara ao operador
("limite mensal de X tokens atingido; usado Y") e, se desejado, num evento de
auditoria de degradação, sem fazer parsing de texto de erro. Uma exceção
específica também separa "quota" de falhas de infraestrutura (banco, rede), que
devem ser tratadas de forma diferente.

**5. Isolamento por empresa em toda leitura e escrita**

`total_tokens_desde` filtra sempre por `UsageRecord.empresa_id`, e o
`EmpresaScopedRepository` é a base que garante esse hábito na camada de dados.
Não existe caminho em `metering` que some empresas juntas. O teste
`test_check_quota_isola_entre_empresas` fixa o comportamento: a empresa B, sem
consumo, tem folga mesmo com a empresa A no teto — a quota é um direito do
contrato de cada tenant, não um balde global.

**6. SQL confinado ao repositório; `metering` só orquestra**

`metering.py` não contém `select`, `where` ou agregação: ele compõe
`UsageRepository` e aplica a política. A soma (`func.coalesce(func.sum(...), 0)`,
incluindo o zero quando não há linhas) vive em `repositories/telemetry.py`, a
única porta de banco prevista no AGENTS.md. Isso mantém a regra de negócio
testável sem banco real, evita dialeto específico fora da camada de persistência e
respeita a fronteira `apps → libs`: `copilot/` é entrada/serviço e depende de
`repositories/`, nunca o contrário.

**7. Datas conscientes de fuso, com falha explícita**

Todas as colunas temporais usam `DateTime(timezone=True)` e o caminho padrão
deriva de `datetime.now(UTC)`. `uso_no_mes` rejeita com `ValueError` um `agora`
sem `tzinfo`: um `datetime` naive seria interpretado de forma diferente no SQLite
dos testes (tratado como UTC) e no Postgres de produção (fuso do servidor),
deslocando o corte do mês e, com ele, o que a empresa "já gastou". Como o cálculo
alimenta um bloqueio, falhar alto é mais seguro do que bloquear (ou liberar) por
um mês errado.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **O bloqueio é best-effort, não atômico.** Se a empresa está a poucos tokens do
  teto, a chamada permitida ainda pode ultrapassá-lo, porque o custo real só é
  conhecido *depois* da resposta. Uma reserva pré-call (estimar o custo máximo)
  evitaria o overshoot, mas exigiria conhecer o tokenizador e o tamanho da
  resposta — complexidade que não se paga no MVP. O teto atua como freio, não como
  fatura exata.
* **`>=` bloqueia ao atingir, não só ao exceder.** É a interpretação conservadora
  e a que o teste documenta (`test_check_quota_bloqueia_ao_atingir`). Preferimos
  bloquear cedo a liberar uma última chamada e terminar acima do contratado.
* **A janela é o mês calendário por `created_at`, não a competência de
  faturamento.** Não há tabela de períodos de cobrança; o mês civil é previsível e
  suficiente para o MVP. Ciclos de faturamento customizados ficam para quando
  existir cobrança de verdade.
* **Concorrência não é tratada.** Duas requisições simultâneas podem ler o mesmo
  uso e ambas passarem pelo `check_quota`. Sem `SELECT ... FOR UPDATE` nem
  contadores atômicos, o limite pode ser levemente furado sob corrida. Aceito no
  MVP (baixo volume); a T28 pode endurecer se necessário.
* **`record_usage` não confirma a transação.** O módulo depende do chamador para
  o `commit`. Isso é intencional (mesma unidade de trabalho) e é o gancho da T28,
  mas significa que um uso registrado e não confirmado é descartado — o que é o
  comportamento correto quando o turno falha.
* **A retenção de `UsageRecord` não é tratada aqui.** A T26 deixou explícito que
  o histórico de custo tem política própria; esta task apenas lê e escreve. Definir
  seu expurgo é decisão separada.

## 4. O que vem a seguir (Roadmap Imediato)

* **T28 (Integrar uso/quota no copiloto):** chamar `check_quota` antes do LLM,
  registrar `record_usage` com os tokens/modelo devolvidos pelo provedor e deixar
  o `registrar_turno` confirmar a transação — fechando o encaixe preparado aqui.
  `QuotaExcedida` vira mensagem clara na borda HTTP e, idealmente, evento de
  auditoria de degradação no catálogo da T26.
* **T30 (KPIs):** consumir `UsageRepository.total_tokens` (all-time) e
  `total_tokens_desde` para relatórios de custo por empresa e período.
* **Retenção de telemetria:** definir prazo (por tenant) para `UsageRecord` e
  `AuditLog`, hoje preservados além do dado conversacional.
* **Endurecimento da concorrência:** se o produto passar a ter picos, avaliar
  reserva de tokens ou contador atômico para tornar o bloqueio estrito.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio e isolamento:** `test_record_usage_soma_por_empresa`
  prova a soma por tenant; `test_check_quota_isola_entre_empresas` prova que o
  teto de A não afeta B; `test_uso_no_mes_soma_apenas_mes_corrente` prova que o
  mês anterior não conta; `test_check_quota_permite_abaixo` e
  `test_check_quota_bloqueia_ao_atingir` fixam a fronteira; e
  `test_uso_no_mes_rejeita_datetime_sem_fuso` cobre o guard de fuso. Nenhum teste
  toca rede/Ollama; todos usam a sessão de teste. `record_usage` rejeita tokens
  negativos (`test_record_usage_rejeita_tokens_negativos`), impedindo que um
  registro corrompido "devolva" quota indevidamente.
* **Cobertura e testes automatizados:** `tests/copilot/test_metering.py` (8
  casos). Execução focada
  `tests/copilot tests/audit tests/test_repositories.py`: **50 passed**. Gate
  completo: **195 passed**, cobertura **97,95%**, com `copilot/metering.py` e
  `repositories/telemetry.py` em **100%**.
* **Padrões de qualidade:** `uv run python -m black --check src/ tests/` → 84
  arquivos inalterados; `uv run python -m ruff check src/ tests/` → All checks
  passed. `from __future__ import annotations` presente, docstrings e nomes em
  português, sem comentários fora de docstring, sem `print`, funções abaixo de 50
  linhas, aninhamento abaixo de 4 níveis, imports na direção permitida
  (`copilot → repositories/libs`), sem SQL em `metering/` e sem integração no
  copiloto (escopo da T28).

## Achados corrigidos no self-review

* **Docstring de `UsageRepository.total_tokens_desde` com erro de concordância
  (leve):** "consumidos pelo empresa" passou a "consumidos pela empresa". Sem
  impacto de comportamento; ajuste de clareza no texto que descreve a nova janela
  de soma.
* **Sem demais achados** de lint, formatação, tenancy, fronteira de camada,
  semântica de janela/fuso ou valor hardcoded. A semântica `usado >= quota` foi
  avaliada e mantida como bloqueio conservador ao atingir o teto; nenhuma
  alteração de comportamento foi necessária e os caminhos cobertos por teste
  permanecem intactos.
