# ADR: t26-auditoria-retencao

## 1. Contexto & Objetivo

A história P1 "Privacidade, retenção e auditoria" assume dois compromissos de
LGPD no MVP: o dado pessoal não sai para o provedor **e** existe trilha do que
aconteceu. As tasks T24/T25 já fecharam a primeira metade (a pergunta é redigida
antes do LLM e o histórico guarda a versão minimizada), mas a segunda metade
ainda estava no papel. A tabela `audit_log` e o `AuditRepository` existiam desde a
T5, porém nada os usava; `Empresa.retention_days` existia no schema, mas nenhuma
rotina o respeitava. Na prática, uma pergunta com PII era redigida — e então não
sobrava registro de que o copiloto foi usado, nem de que uma recomendação foi
emitida; e as conversas cresciam indefinidamente, mesmo com um prazo contratado.

A T26 fecha os critérios **SEC-02** (*"WHEN o tenant define um período de retenção
THEN o sistema SHALL respeitá-lo para conversas e dados armazenados"*) e
**SEC-03** (*"WHEN ocorre uma interação relevante (pergunta, recomendação, aceite,
importação) THEN o sistema SHALL registrar em auditoria por tenant"*). O desafio
de projeto não é gravar uma linha a mais: é registrar a interação **sem virar um
segundo vazamento de PII** — a trilha não pode virar atalho para o dado sensível
que a T25 acabou de tirar de circulação — e purgar dados **sem cruzar a fronteira
entre empresas** nem quebrar a integridade referencial. Ao mesmo tempo, o SQL
precisa continuar confinado a `db/` + `repositories/` (AD-012): `audit/` pode
orquestrar a política, nunca escrever SQL.

## 2. Decisões de Arquitetura

**1. Catálogo fechado de eventos, validado na entrada — `audit/eventos.py`**

`EVENTO_PERGUNTA`, `EVENTO_RECOMENDACAO`, `EVENTO_FEEDBACK` e `EVENTO_IMPORTACAO`
formam a tupla `EVENTOS`, e `registrar_evento(session, empresa_id, evento, user_id,
detalhe)` rejeita com `ValueError` qualquer valor fora dela antes de delegar ao
`AuditRepository`. A coluna `AuditLog.evento` é um `String(60)` livre; sem o
catálogo, cada chamada poderia inventar um rótulo e a trilha perderia valor de
consulta exatamente quando mais importa (uma auditoria). O catálogo é a
materialização de SEC-03 em código: os quatro eventos da história estão
declarados, `feedback` e `importacao` já prontos para as tasks que vão ligá-los, e
a validação garante que um erro de digitação falhe cedo, na unidade de trabalho,
em vez de gravar lixo no banco. A escolha por constantes Python (e não um `Enum`
de banco ou uma migration) mantém a extensão barata: acrescentar um evento é uma
linha na tupla, sem DDL, porque o schema já era genérico.

**2. A auditoria entra na mesma transação do turno, não depois dele**

`CopilotService.answer` chama `_registrar_auditoria(...)` imediatamente antes de
`registrar_turno(...)`. O ponto decisivo é que `registrar_evento` **não** faz
commit: ele apenas adiciona e dá `flush` via `AuditRepository`; o `commit` continua
sendo o de `registrar_turno`, que já fechava a unidade de trabalho. Com isso, ou o
turno (pergunta, resposta e recomendação) e seus eventos de auditoria entram
juntos, ou não entra nada. Essa atomicidade é o que atende ao *"não se perde"*: não
existe janela em que o operador recebeu resposta mas a trilha ficou sem o registro,
nem evento órfão de um turno que falhou. A ordem — auditoria antes das mensagens —
é deliberada: se a gravação do turno estourar, o rollback derruba também os
eventos, mantendo a trilha fiel ao que de fato foi persistido. É a mesma
propriedade que a ADR da T20 já tinha fixado para pergunta e resposta, agora
estendida ao log.

**3. O `detalhe` carrega metadados, nunca o valor — fechando SEC-01 AC3/SEC-02**

Para a pergunta, o detalhe é `{"dominio": ..., "pii": [categorias]}`; para a
recomendação, `{"dominio": ..., "fontes": [...]}`. As categorias vêm de
`redaction.categorias`, que são os identificadores `"nome"`, `"endereco"` e
`"telefone"` produzidos pela T24 — nunca o texto. O teste da P1
(`spec.md`, *Independent Test*) pede verificar no log de auditoria que o texto
enviado ao LLM não contém a PII; a leitura mais forte desse critério é **não
guardar o texto na trilha**, e não guardá-lo parcialmente redigido. Guardar a
versão redigida seria melhor que a crua, mas ainda replicaria o dado sensível em
um segundo lugar, sob outra política de acesso e outra retenção; registrar apenas
a *categoria* responde "houve PII e de que tipo" (visibilidade operacional para
LGPD) sem responder "qual era a PII", que é justamente o que não se quer reter. A
prova comportamental de que o modelo recebeu texto sem PII continua sendo o teste
da T25, que inspeciona as mensagens efetivamente entregues ao `FakeChatModel`.
Assim, SEC-01 AC3 e SEC-02 são cumpridos sem duplicar o dado que a minimização
retirou.

**4. Retenção por empresa com fallback ao default — `audit/retencao.py`**

`retencao_dias(empresa, settings)` devolve `empresa.retention_days` quando
definido e cai para `Settings.default_retention_days` quando for `None`;
`purgar_expiradas(session, agora, settings)` percorre todas as empresas via novo
`EmpresaRepository.list_all()`, calcula um `limite` distinto por empresa
(`momento - timedelta(days=retencao_dias(...))`) e chama
`ConversationRepository.purgar_expiradas(empresa.id, limite)`. É SEC-02 na
íntegra: o prazo é do tenant, não global. O fallback existe porque nem toda
empresa configura retenção no onboarding; o default de 365 dias (já em `Settings`)
dá um comportamento previsível. O isolamento é garantido em duas camadas: a lista
de empresas vem do repositório, e cada deleção é filtrada por `empresa_id` **e**
pelos ids de conversa daquela empresa. Uma empresa de 30 dias nunca enxuga os
dados de uma de 365, e o teste `test_purga_isola_entre_empresas` fixa isso.

**5. SQL confinado ao repositório, deleção na ordem das FKs**

O `audit/` não contém `select`/`delete`: a política compõe repositórios. O SQL de
purga vive em `ConversationRepository.purgar_expiradas`, que remove na ordem
`Feedback → Recommendation → Message → Conversation`, sempre ancorado nos ids de
conversa já filtrados por `empresa_id`. A ordem segue as dependências do schema
(`feedback.recommendation_id → recommendation.conversation_id →
message.conversation_id → conversation.id`) e evita tanto violação de FK quanto
linhas órfãs. A implementação lê os ids primeiro e emite `DELETE`s sucessivos em
vez de usar `DELETE ... USING`/subdeleção única: é a forma portável que se comporta
igual no SQLite dos testes e no Postgres de produção, sem depender de sintaxe
específica de dialeto. Também não há `cascade` ORM a depender: a purga é explícita,
o que a torna auditável e independente do estado de carregamento da sessão.

**6. A purga é uma operação explícita, não um agendador**

`purgar_expiradas` é uma função de serviço, confirmada com `commit` no final, que
deve ser chamada por quem opera retenção (job, CLI ou rotina administrativa de uma
task futura). O MVP não tem worker/cron, e acoplar uma deleção destrutiva ao
caminho da requisição seria pior: ela ficaria sujeita à latência e à concorrência
do tráfego, e mascararia a decisão operacional de quando purgar. Deixá-la explícita
também a torna testável de ponta a ponta e idempotente. Deliberadamente **fora** do
escopo da purga: `UsageRecord` (histórico de custo/consumo, com política própria na
T27/T28), `AuditLog` (a trilha legal precisa sobreviver ao dado conversacional que
ela documenta — apagar a evidência junto com o objeto seria o oposto de auditar) e
os artefatos de importação (`ImportJob`/`ImportJobError`). Cada um desses tem
sensibilidade e semântica de retenção diferentes e merece decisão própria.

**7. Datas conscientes de fuso, com falha explícita**

Todas as colunas temporais usam `DateTime(timezone=True)` e o default `_agora()`
devolve `datetime.now(UTC)`. O corte da retenção é calculado em Python (aware) e a
comparação acontece em SQL. No Postgres, `timestamptz` preserva o instante; no
SQLite dos testes, o fuso é descartado no armazenamento, mas como todos os valores
são UTC o ordenamento permanece consistente — e o teste de purga de 60 dias contra
prazo de 30 prova isso na prática. Para eliminar o risco do caso não coberto, um
`agora` sem fuso passou a levantar `ValueError`: um `datetime` naive entregue a uma
operação destrutiva seria interpretado no fuso do servidor no Postgres (ou
silenciosamente comparado como UTC no SQLite) e deslocaria o corte sem aviso.
Falhar alto é o comportamento certo para uma rotina que apaga dados.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **A purga decide pela idade da conversa, não de cada registro.** O corte usa
  `Conversation.created_at`; mensagens e recomendações são removidas por
  pertencerem à conversa expirada, mesmo que tenham sido criadas depois. É a
  unidade que o produto e o schema tratam como "a conversa", e mantê-la coesa
  evita estados em que uma conversa "viva" perde metade das mensagens. Uma
  mensagem nova em conversa antiga é rara no MVP (uma conversa por usuário);
  aceito.
* **A trilha de auditoria não guarda o conteúdo auditado.** A visibilidade fica
  reduzida às categorias e à contagem — não é possível reconstruir "o que foi
  perguntado" a partir do log. É a consequência intencional de não reter PII; para
  conformidade, saber que houve PII de nome/telefone já é o dado exigido, e o
  detalhe completo do turno continua no histórico minimizado.
* **A retenção não cobre `UsageRecord`, `AuditLog` nem importação.** O MVP
  preserva a trilha legal e o histórico de custo além do dado conversacional.
  Isso tem custo de armazenamento e é uma decisão de compliance, não de
  performance; políticas específicas ficam para tasks seguintes.
* **Não há purga automática.** A política existe, mas depende de execução
  explícita; enquanto não houver agendador, uma empresa com prazo curto não é
  purgada sozinha. Seguro para o MVP (sem WMS/ERP com grandes volumes) e
  deliberadamente visível.
* **O catálogo é validado no serviço, não no repositório.** `AuditRepository.record`
  continua aceitando qualquer `evento`; quem chamar o repositório direto contorna o
  catálogo. A porta de negócio é `registrar_evento`, e a fronteira `apps → audit →
  libs` mantém o uso direto restrito à própria camada.
* **`dominio` e `fontes` vão para o detalhe.** São referências de negócio (nome do
  especialista, rótulos de fonte), não PII. Se um rótulo de fonte puder conter dado
  pessoal no futuro, a política de auditoria precisa ser reavaliada junto com a
  T24.

## 4. O que vem a seguir (Roadmap Imediato)

* **T27/T28 (Medição de uso e quota):** registrar `UsageRecord` na mesma
  transação do turno, reaproveitando o encaixe da auditoria, e definir a retenção
  própria desses registros.
* **T22/T13 (Feedback e importação):** usar `EVENTO_FEEDBACK` e
  `EVENTO_IMPORTACAO`, já no catálogo, para completar o SEC-03 nos quatro eventos
  da história.
* **Agendamento da purga:** job/CLI/admin que chame `purgar_expiradas` e,
  idealmente, registre o próprio ato de purgar como evento de manutenção em
  `AuditLog`.
* **Eventos de degradação:** o `design.md` prevê auditoria para timeout de LLM e
  quota excedida; o catálogo é o ponto de extensão.
* **Retenção para trilha e custo:** definir se `AuditLog`/`UsageRecord` também
  expiram (e por tenant) quando houver requisito legal/contratual explícito.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio e privacidade:** o registro de eventos é escopado por
  `empresa_id` vindo da sessão autenticada, e `AuditRepository.list` filtra pelo
  tenant — `test_registrar_evento_persiste_por_empresa` prova que um evento de A
  não aparece para B. O detalhe não carrega PII: `test_answer_registra_auditoria_sem_pii`
  afirma o conjunto de categorias `{"nome", "telefone"}` e a **ausência** de
  `"João"` no `detalhe`. A atomicidade é observável: os testes leem os eventos
  após `answer`, ou seja, confirmados junto do turno. A purga respeita a ordem de
  FKs e o isolamento (`test_purga_remove_conversa_e_dependentes`,
  `test_purga_isola_entre_empresas`), preserva o que está dentro do prazo
  (`test_purga_preserva_dentro_do_prazo`) e usa o prazo da empresa com fallback ao
  default (`test_retencao_usa_prazo_da_empresa`,
  `test_retencao_usa_padrao_quando_empresa_sem_prazo`,
  `test_purga_usa_padrao_do_sistema`). Nenhum teste toca rede/Ollama.
* **Cobertura e testes automatizados:** `tests/audit/test_auditoria.py` (9 casos,
  incluindo o guard de fuso) e 2 casos novos em `tests/copilot/test_service.py`.
  Execução focada `tests/audit tests/copilot tests/test_repositories.py`:
  **43 passed**. Gate completo: **188 passed**, cobertura **97,91%**, com
  `audit/eventos.py` e `audit/retencao.py` em **100%**.
* **Padrões de qualidade:** `uv run python -m black --check src/ tests/` → 82
  arquivos inalterados; `uv run python -m ruff check src/ tests/` → All checks
  passed. `from __future__ import annotations` presente, docstrings e nomes em
  português, sem comentários fora de docstring, sem `print`, funções abaixo de 50
  linhas, aninhamento abaixo de 4 níveis e imports na direção permitida
  (`apps → audit → libs`), sem SQL em `audit/`.

## Achados corrigidos no self-review

* **`purgar_expiradas` aceitava `agora` sem fuso (média, risco de corte
  silenciosamente errado):** a comparação acontece em SQL, então um `datetime`
  naive não falha — ele é interpretado de formas diferentes no SQLite (tratado
  como UTC) e no Postgres (tratado no fuso do servidor), deslocando o limite de
  purga em horas. Como se trata de uma operação destrutiva, o parâmetro passou a
  levantar `ValueError` quando `tzinfo is None`, e
  `test_purga_rejeita_datetime_sem_fuso` cobre a rejeição. O caminho padrão segue
  usando `datetime.now(UTC)`.
* **Sem demais achados** de lint, formatação, tenancy, fronteiras de camada,
  PII no detalhe ou ordem de FKs; nenhuma outra correção foi necessária e não
  houve mudança de comportamento nos caminhos já cobertos por teste.
