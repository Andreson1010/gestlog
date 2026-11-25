# Segurança Sweep — quitação de 1 CRITICAL + 13 IMPORTANTES — Technical Spec

**Path:** `docs/specs/features/seguranca-sweep/spec.md`
**TLC scope:** complex
**Based on story:** épico de varredura de segurança: quota/metering (C-1, I-7, I-8), identidade de convite/cadastro (I-1..I-4), PII/LGPD (I-5, I-10, I-11), prompt injection/fontes (I-6), unicidade de histórico (I-9) e config/rede LLM fail-closed (I-12, I-13) — 6 tasks, 1 PR cada contra `feat/seguranca-sweep`.
**Status:** Awaiting human approval

---

## Problem Statement

Uma varredura de segurança encontrou 1 CRITICAL e 13 achados IMPORTANTES: tokens do
supervisor não são contabilizados na quota (C-1), uso sem `usage_metadata` conta 0
(I-7), a sequência check+record da quota tem corrida (I-8), e-mails divergentes por
caixa/espaço criam identidades duplicadas (I-1), `/cadastro` não tem rate limit
(I-2), a resposta de criação de convite enumera e-mails registrados (I-3),
`is_verified` nasce `True` (I-4), e-mail/CPF/CNPJ não são redigidos antes do LLM
(I-5), o e-mail de convites expirados/usados nunca é purgado (I-10),
`retention_days <= 0` faz a rotina purgar tudo silenciosamente (I-11), marcadores
`Fontes:` vindos de dado importado são interpretados como estrutura da resposta
(I-6) e a `conversation` aceita duplicatas por falta de constraint (I-9). Sem
`llm_timeout_s`/`llm_max_retries` a chamada LLM pode pendurar indefinidamente (I-12)
e a validação de segredo só dispara com `AMBIENTE=prod` explicitamente definido —
um deploy que esqueça a env sobe com segredo público (I-13). O épico quita os 14
achados em 6 tasks independentes, sem abrir nenhum escopo novo de produto.

## Goals

- [ ] Todo consumo de LLM do turno (supervisor **e** especialistas) é contabilizado
      e registrado por empresa, mesmo sem `usage_metadata` (nunca 0).
- [ ] A quota por empresa é aplicada de forma serializada: uma corrida resolve com
      exatamente um vencedor; a empresa B nunca é bloqueada pela A.
- [ ] Identidade: e-mail é normalizado (strip/casefold) em comparação e
      persistência, com unicidade provada nos dois dialetos.
- [ ] Nenhuma resposta HTTP revela se um e-mail já é registrado na criação de
      convites; conflito fica só em log de servidor.
- [ ] PII (e-mail, CPF, CNPJ) nunca chega ao provedor de LLM nem ao histórico.
- [ ] Dado importado contendo `Fontes:` não vira estrutura da recomendação; fontes
      persistidas refletem as tools realmente consultadas no turno.
- [ ] `conversation` tem unicidade `(empresa_id, user_id)` com upgrade/downgrade
      provados e `get_or_create` tolerante a corrida.
- [ ] A configuração é fail-closed: segredo público não sobe em execução de
      produção, detectada independentemente de `AMBIENTE`; segredos são `SecretStr`.

## Out of Scope

| Feature | Reason |
| --- | --- |
| Achados LOW da varredura (CSRF token, rate limit por conta/proxy, `pool_pre_ping`, dedup `ItemCorrecao`, validações em telemetry, regex de telefone, renomear `get_sync_session`, refatoração de fronteiras) | Decisão do autor: épico cobre só CRITICAL+IMPORTANTES |
| Fluxo de e-mail/verificação de conta (`is_verified` exigido em rota) | Decisão humana 3: verificação segue no roadmap; aqui só nasce `False` |
| Reset/backfill da quota histórica ao introduzir quota por empresa | Decisão humana 2: consumo histórico conta contra a nova quota, sem reset |
| Aceite de convite para e-mail já registrado (fluxo autenticado futuro) | AD-015/L-048: guard atual preservado; não é reaberto |
| Store compartilhado de rate limit (Redis) / múltiplas réplicas | Escala futura; padrão atual em memória é suficiente |
| Migração/dedup automática de dados existentes (conversas, e-mails) | Decisões humanas 4: fail-fast listando conflitos, resolução manual |

---

## User Stories

### P1: Quota e metering confiáveis por empresa (Task 1) ⭐ MVP

**User Story**: Como administrador do SaaS, quero que todo consumo de LLM de um
turno (roteamento do supervisor incluído) seja contabilizado por empresa e que a
quota mensal bloqueie o uso com um erro explícito, para que a conta da empresa
reflita o uso real e estoure de forma previsível.

**Why P1**: C-1 é o achado CRITICAL — sem os tokens do supervisor, a quota é furável
e o custo real diverge do medido.

**Acceptance Criteria**:
1. WHEN o supervisor roteia uma consulta THEN o sistema SHALL somar os tokens dessa
   chamada (reportados ou estimados) em `tokens_usados` do estado do grafo (C-1 →
   `QUO-01`).
2. WHEN uma resposta do modelo vem sem `usage_metadata` (ou com `total_tokens` 0) THEN
   o sistema SHALL estimar `max(1, len(texto) // 4)` tokens por mensagem; para texto
   não vazio a contagem SHALL nunca ser 0 (I-7 → `QUO-02`).
3. WHEN o turno executa a sequência check→LLM→record THEN o sistema SHALL serializar
   check e record por empresa (lock de linha), de modo que uma corrida de dois
   turnos da mesma empresa resolva com exatamente um vencedor e o excedente seja
   bloqueado ou registrado dentro da quota (I-8 → `QUO-03`).
4. WHEN a empresa tem `token_quota_mensal` definida THEN o sistema SHALL usar esse
   valor como quota; WHEN é `NULL` THEN SHALL usar o teto de `Settings`
   (decisão humana 1 → `QUO-04`).
5. WHEN o somatório global do mês atinge o teto global THEN o sistema SHALL bloquear
   novos turnos como salvaguarda (decisão humana 1 → `QUO-05`).
6. WHEN a quota é atingida THEN o sistema SHALL devolver a mensagem explícita de
   quota (nunca 500) e SHALL chamar o modelo (I-8/C-1 → `QUO-06`).
7. WHEN o consumo histórico é avaliado contra a nova quota THEN o sistema SHALL
   contá-lo sem reset nem backfill (decisão humana 2 → `QUO-04`).

**Independent Test**: dois turnos da mesma empresa em paralelo (Postgres de teste)
produzem exatamente um registro por turno e a soma não excede a quota; um turno
só-supervisor (rota FINISH direta com modelo fake) registra `tokens_usados > 0`;
empresa B continua respondendo enquanto A esgota a quota.

---

### P1: Identidade de cadastro e convite (Task 2) ⭐ MVP

**User Story**: Como pessoa que se cadastra ou é convidada, quero que meu e-mail
seja tratado de forma canônica (sem duplicar por caixa/espaço) e que a criação de
convites não revele quem já tem conta, para que minha identidade seja única e não
enumerável.

**Why P1**: I-1..I-4 atacam a superfície pública (cadastro/convite) — enumerate de
usuários e identidade duplicada.

**Acceptance Criteria**:
1. WHEN um e-mail entra por `/cadastro`, `/onboarding`, convite ou aceite THEN o
   sistema SHALL normalizar (strip + casefold) antes de comparar e de persistir
   (I-1 → `IDT-01`).
2. WHEN dois cadastros divergem apenas por caixa/espaço no e-mail THEN o sistema
   SHALL recusar o segundo como "já cadastrado" (`IDT-01`).
3. WHEN a migração cria o índice único funcional em `lower(email)` THEN duplicatas
   pré-existentes SHALL abortar a migração (fail-fast) listando os conflitos para
   resolução manual (decisão humana 4 → `IDT-02`).
4. WHEN `POST /cadastro` recebe tentativas em rajada THEN o sistema SHALL aplicar o
   rate limit da janela configurada (I-2 → `IDT-03`).
5. WHEN um admin convida um e-mail já registrado THEN o sistema SHALL devolver a
   MESMA resposta de sucesso (mesma shape, mesmo status) que para e-mail novo, e o
   conflito SHALL aparecer apenas em log de servidor (decisão humana 8 → `IDT-04`).
6. WHEN uma conta nasce (cadastro ou aceite de convite) THEN `is_verified` SHALL
   nascer `False`, sem quebrar nenhum fluxo autenticado atual (decisão humana 3 →
   `IDT-05`).

**Independent Test**: `Ana@X.com` e `ana@x.com ` disputam a mesma identidade (segundo
recusado); convidar e-mail registrado e inexistente devolve respostas
indistinguiveis (e o token do conflito não aceita); `is_verified` é `False` no
banco após cadastro e aceite.

---

### P1: PII e LGPD no fluxo do copiloto (Task 3) ⭐ MVP

**User Story**: Como titular de dados (dono da empresa), quero que e-mail, CPF e
CNPJ sejam redigidos antes de qualquer texto ir ao LLM, que o e-mail de convites
usados/expirados seja purgado e que `retention_days` inválido JAMAIS apague dados,
para que a LGPD seja respeita do fim ao fim.

**Why P1**: I-5 vaza PII direta ao provedor pago; I-11 é fail-open hoje (purga tudo).

**Acceptance Criteria**:
1. WHEN a pergunta do usuário contém e-mail, CPF ou CNPJ THEN o sistema SHALL
   redigi-los por regex antes do envio ao LLM e registrar as categorias na
   auditoria do turno (I-5 → `PII-01`).
2. WHEN o texto redigido vai ao histórico THEN nenhuma ocorrência original de
   e-mail/CPF/CNPJ SHALL ser persistida (`PII-01`).
3. WHEN um convite está expirado (`expira_em` passado) ou usado (`usado_em` não
   nulo) THEN a rotina de retenção SHALL substituir `Convite.email` por valor vazio,
   preservando o restante da linha para auditoria (I-10 → `PII-02`).
4. WHEN a empresa tem `retention_days <= 0` THEN a rotina SHALL recusar purgar os
   dados dessa empresa, SHALL logar o erro e SHALL continuar com as demais
   empresas (decisão humana 5 → `PII-03`).
5. WHEN uma nova `Empresa` tenta gravar `retention_days <= 0` THEN o sistema SHALL
   recusar tanto no repositório (`ValueError`) quanto no banco (CheckConstraint)
   (decisão humana 5 → `PII-04`).

**Independent Test**: pergunta com e-mail+CPF+CNPJ sai redigida (marcadores
`[EMAIL]`/`[DOCUMENTO]`) no histórico e na auditoria; purga zera o e-mail de
convites vencidos; `retention_days=0` não purga a empresa e o `INSERT` é recusado
pela constraint nos dois dialetos.

---

### P1: Fontes à prova de prompt injection (Task 4) ⭐ MVP

**User Story**: Como operador do copiloto, quero que marcadores como `Fontes:` vindos
de dados importados nunca sejam interpretados como estrutura da resposta e que as
fontes persistidas reflitam só o que as tools realmente consultaram, para que uma
importação maliciosa não falsifique a origem das recomendações.

**Why P1**: I-6 deixa o atacante, via dado de tool, controlar a trilha de fontes.

**Acceptance Criteria**:
1. WHEN um conteúdo de `ToolMessage` intermediário contém marcador de estrutura
   (`Fontes:` em início de linha) THEN o sistema SHALL neutralizá-lo antes de o
   modelo ver (I-6 → `FNT-01`).
2. WHEN a resposta composta contém linha de `Fontes:` no meio do corpo (vinda de
   dado) THEN o parser SHALL considerar estrutura apenas a linha final, e o
   marcador injetado SHALL permanecer texto literal, não interpretado (I-6 →
   `FNT-01`).
3. WHEN nenhum tool foi consultado no turno THEN as fontes persistidas SHALL ser
   vazias, logando divergência se o texto trouxer fontes (decisão humana 6 →
   `FNT-02`).
4. WHEN tools foram consultadas THEN as fontes persistidas SHALL ser as extraídas
   da resposta, mantidas apenas quando consistentes com o turno; divergência SHALL
   ser logada e nunca SHALL recusar o turno (decisão humana 6 → `FNT-02`).

**Independent Test**: fornecedor importado com nome contendo `\nFontes: https://mal`
produz recomendação cujas fontes persistidas são as legítimas da tool; turno
só-supervisor persiste `fontes=()` com log de divergência.

---

### P1: Unicidade da conversa do usuário (Task 5) ⭐ MVP

**User Story**: Como usuário do copiloto, quero ter exatamente uma conversa por
empresa, garantida pelo banco e tolerante a corrida, para que meu histórico nunca
se divida entre linhas duplicadas.

**Why P1**: I-9 corrige o bug de histórico na raiz (constraint + corrida), não com
paliativo de leitura.

**Acceptance Criteria**:
1. WHEN a migração do épico aplica a constraint THEN `conversation` SHALL ficar com
   `UniqueConstraint(empresa_id, user_id)`, provada em upgrade **e** downgrade nos
   dois dialetos (I-9 → `HST-01`).
2. WHEN duplicatas `(empresa_id, user_id)` pré-existentes existem THEN a migração
   SHALL falhar (fail-fast) listando os pares conflitantes para resolução manual
   (decisão humana 4 → `HST-02`).
3. WHEN dois turnos criam a conversa em paralelo THEN `get_or_create` SHALL resolver
   com uma única linha: `IntegrityError` → releitura da conversa existente
   (I-9 → `HST-03`).
4. WHILE duplicatas ainda existirem (antes da migração em algum ambiente) THEN a
   leitura SHALL devolver deterministicamente a conversa mais recente do par
   (I-9 → `HST-04`).

**Independent Test**: migração com par duplicado semeado falha listando os ids; sem
duplicata, upgrade cria a constraint e downgrade a remove (rodada completa);
`get_or_create` concorrente termina com 1 linha e 1 mensagem por turno.

---

### P1: Config e rede LLM fail-closed (Task 6) ⭐ MVP

**User Story**: Como operador do deploy, quero timeout e retries configuráveis na
chamada LLM e uma configuração que recuse subir com segredo público em produção —
mesmo que a env `AMBIENTE` esteja errada ou ausente — para que a falha de
configuração feche a porta, não a abra.

**Why P1**: I-12/I-13 fecham a última superfície do sweep (pendurar rede e segredo
vazado por env esquecida).

**Acceptance Criteria**:
1. WHEN `ChatOpenAI` é construído THEN o sistema SHALL aplicar
   `Settings.llm_timeout_s` (timeout) e `Settings.llm_max_retries` (retries) (I-12 →
   `CFG-01`).
2. WHEN a execução é de produção — `AMBIENTE=prod` OU `database_url` apontando para
   host não-local (heurística independente da env) THEN o sistema SHALL recusar
   subir com `auth_secret` default ou curto (< 32), com erro de validação (I-13 →
   `CFG-02`).
3. WHEN `AMBIENTE=prod` THEN o sistema SHALL recusar `database_url` que não seja
   Postgres (sqlite em prod é erro de validação) (I-13 → `CFG-03`).
4. WHEN `auth_secret` ou `llm_api_key` são inspecionados (repr/serialização/logs)
   THEN o sistema SHALL expor valor mascarado (`SecretStr`), nunca o segredo em
   claro (I-13 → `CFG-04`).

**Independent Test**: `Settings(ambiente="prod", auth_secret=SEGREDO_DEV)` e
`Settings(ambiente="dev", auth_secret=SEGREDO_DEV,
database_url="postgresql+psycopg://...@db.externo/db")` ambos levantam `ValueError`;
`repr(settings)` não contém o segredo nem a api key; chamada de rede pendurada
termina no timeout configurado (contrato do `ChatOpenAI` coberto por teste de
fábrica, não de rede).

---

## Edge Cases

- WHEN dois turnos da mesma empresa disputam a última folga de quota THEN exatamente
  um SHALL vencer (registra e responde) e o outro SHALL ser bloqueado com a mensagem
  de quota — sem 500 e sem registrar além da quota (`EDG-01`, `QUO-03`).
- WHEN a empresa A esgota a própria quota THEN a empresa B SHALL continuar
  respondendo; o lock de serialização é por linha de empresa (`EDG-02`).
- WHEN o turno é só-supervisor (FINISH direto, nenhum especialista) THEN
  `tokens_usados` SHALL ser > 0 (estimativa) e as fontes persistidas SHALL ser
  vazias (`EDG-03`, `QUO-01`, `FNT-02`).
- WHEN dado importado contém `\nFontes: <malicioso>` no meio do texto THEN o
  marcador SHALL não ser interpretado: o parser só reconhece a linha final
  composta pela tool comum (`EDG-04`, `FNT-01`).
- WHEN cadastro usa `Ana@X.COM ` e já existe `ana@x.com` THEN o sistema SHALL
  recusar como já cadastrado — comparação e persistência normalizadas + índice
  funcional (`EDG-05`, `IDT-01/02`).
- WHEN convite é criado para e-mail registrado em case diferente THEN a resposta
  SHALL ser idêntica à de e-mail novo (`EDG-06`, `IDT-04`).
- WHEN `retention_days = 0` THEN nada daquela empresa SHALL ser purgado (conversas,
  correções nem convites); as demais empresas seguem normalmente (`EDG-07`,
  `PII-03`).
- WHEN o aceite de convite mira e-mail registrado THEN o guard atual SHALL
  continuar recusando (defesa do takeover, L-048/AD-015) — mudança genérica vale
  apenas para a CRIAÇÃO de convite (`EDG-08`, `IDT-04`).
- WHEN duplicatas de conversa são detectadas pela migração THEN os ids das linhas
  conflitantes SHALL constar na mensagem de falha (resolução manual documentada no
  ADR da task) (`EDG-09`, `HST-02`).
- WHEN o segredo dev é usado com `database_url` de host externo THEN a aplicação
  SHALL não subir, mesmo com `AMBIENTE=dev` (heurística fail-closed) (`EDG-10`,
  `CFG-02`).
- WHEN `usage_metadata` existe com `total_tokens` 0 THEN o sistema SHALL tratar
  como ausente e estimar (nunca 0 para texto não vazio) (`EDG-11`, `QUO-02`).
- WHEN o consumo histórico pré-existe ao introduzir a quota por empresa THEN ele
  SHALL continuar contando contra a quota (sem reset/backfill) (`EDG-12`,
  `QUO-04`).

---

## Requirement Traceability

| Requirement ID | Achado | Story / Task | Status |
| --- | --- | --- | --- |
| QUO-01 | C-1 | P1 Task 1 | Pending |
| QUO-02 | I-7 | P1 Task 1 | Pending |
| QUO-03 | I-8 | P1 Task 1 | Pending |
| QUO-04 | decisões humanas 1 e 2 | P1 Task 1 | Pending |
| QUO-05 | decisão humana 1 (teto global) | P1 Task 1 | Pending |
| QUO-06 | C-1/I-8 | P1 Task 1 | Pending |
| IDT-01 | I-1 | P1 Task 2 | Pending |
| IDT-02 | I-1 / decisão humana 4 | P1 Task 2 | Pending |
| IDT-03 | I-2 | P1 Task 2 | Pending |
| IDT-04 | I-3 / decisão humana 8 | P1 Task 2 | Pending |
| IDT-05 | I-4 / decisão humana 3 | P1 Task 2 | Pending |
| PII-01 | I-5 | P1 Task 3 | Pending |
| PII-02 | I-10 | P1 Task 3 | Pending |
| PII-03 | I-11 / decisão humana 5 | P1 Task 3 | Pending |
| PII-04 | I-11 / decisão humana 5 | P1 Task 3 | Pending |
| FNT-01 | I-6 | P1 Task 4 | Pending |
| FNT-02 | I-6 / decisão humana 6 | P1 Task 4 | Pending |
| HST-01 | I-9 | P1 Task 5 | Pending |
| HST-02 | I-9 / decisão humana 4 | P1 Task 5 | Pending |
| HST-03 | I-9 | P1 Task 5 | Pending |
| HST-04 | I-9 | P1 Task 5 | Pending |
| CFG-01 | I-12 | P1 Task 6 | Pending |
| CFG-02 | I-13 | P1 Task 6 | Pending |
| CFG-03 | I-13 | P1 Task 6 | Pending |
| CFG-04 | I-13 | P1 Task 6 | Pending |
| EDG-01..EDG-12 | edge cases acima | Edge cases | Pending |

**ID format:** `[AREA]-[NUMBER]` — `QUO` (quota/metering), `IDT` (identidade),
`PII` (LGPD), `FNT` (fontes/injection), `HST` (histórico), `CFG` (config/rede) e
`EDG` (casos-limite).

**Coverage:** 25 requisitos + 12 edge cases; mapeamento achado → requisito completo
(C-1 → QUO-01/03/06; I-1 → IDT-01/02; I-2 → IDT-03; I-3 → IDT-04; I-4 → IDT-05;
I-5 → PII-01; I-6 → FNT-01/02; I-7 → QUO-02; I-8 → QUO-03/06; I-9 → HST-01..04;
I-10 → PII-02; I-11 → PII-03/04; I-12 → CFG-01; I-13 → CFG-02/03/04).

---

## Data Model Changes

Três migrações Alembic encadeadas após `e8a1c5d9f3b7` (head atual), uma por task,
sem colisão de revisions (detalhe e ids em `design.md`):

1. **Task 1** — `Empresa.token_quota_mensal: int | None` (`Integer`, nullable; `NULL`
   → quota global de `Settings`). Nenhuma tabela nova.
2. **Task 2** — índice único funcional `uq_user_email_ci` em `lower(email)` da
   tabela `user` (escrito à mão; suportado por SQLite ≥ 3.9 e Postgres).
3. **Task 3** — `CheckConstraint("retention_days IS NULL OR retention_days >= 1",
   name="ck_empresa_retention_positiva")` em `empresa` (batch para SQLite).
4. **Task 5** — `UniqueConstraint("empresa_id", "user_id", name=
   "uq_conversation_empresa_user")` em `conversation` (batch para SQLite), com
   checagem fail-fast de duplicatas no `upgrade()`.

`Convite` não muda de schema: a purga do e-mail (PII-02) é `UPDATE email = ""` nas
linhas expiradas/usadas, preservando a linha para auditoria. `Settings` ganha
`llm_timeout_s`/`llm_max_retries` (Task 6) — configuração, não migração.

## Process / Background Flow

**Happy path (turno do copiloto, pós-épico):** request autenticada → check de rate
limit (quando aplicável) → lock de linha da empresa (`FOR UPDATE`) → `check_quota`
(quota da empresa ou global, + salvaguarda do teto global) → redação de PII
(agora com e-mail/CPF/CNPJ) → grafo (supervisor + especialistas, todos contando
tokens, tools consultadas acumuladas) → estimativa/contagem de tokens →
`record_usage` → validação das fontes contra as tools consultadas → persistência
do turno na conversa única (`get_or_create` tolerante a corrida) → `commit`
(libera o lock).

**Failure path — quota estourada:** qualquer checagem (empresa, teto global)
levantando `QuotaExcedida` → mensagem explícita de quota, sem chamar o modelo,
sem registrar uso, sem 500.

**Failure path — migração com dados inválidos:** duplicatas de e-mail (Task 2) ou
de conversa (Task 5) → `upgrade()` aborta listando conflitos; resolução é manual
(procedimento no ADR de cada task).

**Failure path — retenção inválida:** `retention_days <= 0` → a rotina recusa
purgar aquela empresa, loga erro e segue as demais; banco e repositório recusam
novos valores.

## API Changes

- `POST /cadastro` (e `POST /onboarding` já limitado): `POST /cadastro` passa a ter
  dependência `limitar("cadastro")` (429 na rajada) — `web/app.py`.
- `POST /empresa/convites`: resposta de sucesso (201, shape
  `{email, papel, token}`) passa a ser idêntica para e-mail registrado e não
  registrado; token devolvido no caso de conflito é decoy inutilizável (nunca
  persistido); conflito só em log de servidor. Nenhum endpoint novo; nenhuma
  assinatura pública muda.

## Frontend Changes

Nenhum. As telas não mudam: a mensagem de quota já existe no chat; normalização de
e-mail, redação e unicidade são invisíveis à UI (o formulário de cadastro
re-renderizado com erro genérico continua o fluxo atual).

## Tests Required

- **Unit:** estimativa de tokens (`max(1, len//4)`, metadata ausente/zero);
  resolução de quota (empresa vs global); normalização de e-mail; regexes de
  e-mail/CPF/CNPJ (ordem e discriminantes); sanitização de marcadores em
  ToolMessage e parsing só-da-última-linha; validação de fontes vs tools
  consultadas; heurística fail-closed de produção; `SecretStr` mascarado.
- **Integration:** corrida de quota (duas sessões Postgres de teste — exatamente um
  vencedor); lock por empresa (B não bloqueada); rate limit em `/cadastro`; convite
  com resposta idêntica; `is_verified=False` após cadastro/aceite; purga de
  `Convite.email`; constraint de retention (insert recusado nos dois dialetos);
  `get_or_create` com `IntegrityError` → releitura; migrações 1–4 com upgrade **e**
  downgrade e 1 asserção por coluna/efeito (L-037).
- **Edge case:** turno só-supervisor (contado, fontes vazias); texto injetado com
  `Fontes:` no meio do corpo; `usage_metadata` zero; duplicatas semeadas abortando
  migração com lista de conflitos; segredo dev + host externo não sobe; sqlite em
  prod não sobe.
- **Existing tests to update:** `tests/conftest.py` (`FakeChatModel.with_structured_output`
  passa a devolver o shape `{"raw", "parsed"}` do `include_raw=True`); testes de
  settings que comparam `auth_secret`/`llm_api_key` como `str` (passam a
  `.get_secret_value()`); testes de metering (assina novas funções de quota);
  testes de `enviar_resposta_logistica`/parsing do service; testes de migrations
  (4 novas revisions); nenhum teste deve tocar rede/Ollama.

## Files That Will Change

| File | Change type | Why |
| --- | --- | --- |
| `src/gestlog/config.py` | modify | `llm_timeout_s`, `llm_max_retries`, `SecretStr`, validador fail-closed (T6) |
| `src/gestlog/llm.py` | modify | Passa `timeout`/`max_retries` ao `ChatOpenAI`; api_key como SecretStr (T6) |
| `src/gestlog/auth/backend.py`, `src/gestlog/auth/manager.py` | modify | `auth_secret.get_secret_value()` (T6) |
| `src/gestlog/auth/accounts.py` | modify | Normalização de e-mail, `is_verified=False` (T2) |
| `src/gestlog/web/app.py` | modify | Rate limit em `POST /cadastro` (T2) |
| `src/gestlog/web/onboarding.py` | modify | Resposta de convite genérica + log (T2) |
| `src/gestlog/db/models.py` | modify | `Empresa.token_quota_mensal`, CheckConstraint retention, índice `lower(email)`, `UniqueConstraint` conversation (T1/T2/T3/T5) |
| `alembic/versions/` (4 novas) | new | Migrações encadeadas (T1/T2/T3/T5) |
| `src/gestlog/agents/base.py` | modify | Helper público de tokens+estimativa, sanitização de ToolMessage, `tools_consultadas` (T1/T4) |
| `src/gestlog/agents/supervisor.py` | modify | `include_raw=True`, contagem de tokens do supervisor (T1) |
| `src/gestlog/state.py` | modify | `tools_consultadas` no `AgentState` (T4) |
| `src/gestlog/copilot/metering.py` | modify | Quota por empresa, lock `FOR UPDATE`, teto global (T1) |
| `src/gestlog/copilot/service.py` | modify | Lock na empresa, validação de fontes, parsing da última linha (T1/T4) |
| `src/gestlog/privacy/{redacao,politica}.py` | modify | Regexes e-mail/CPF/CNPJ + categorias (T3) |
| `src/gestlog/audit/retencao.py` | modify | Fail-safe `retention_days<=0`, purga de `Convite.email` (T3) |
| `src/gestlog/repositories/empresas.py` | modify | Validação de `retention_days`/`token_quota_mensal` no create (T1/T3) |
| `src/gestlog/repositories/conversations.py` | modify | `get_or_create` com savepoint, leitura mais recente (T5) |
| `tests/conftest.py` | modify | `FakeChatModel` com shape `include_raw` (T1) |
| `tests/...` | new/modify | Ver "Tests Required" |

## Risks

- **Lock de quota mantido durante a chamada LLM:** o `FOR UPDATE` na linha da
  empresa fica preso até o commit, que inclui a resposta do modelo. Mitigação: a
  janela é limitada por `llm_timeout_s` (T6, mesma integração — antes de T6 o risco
  de pendura já existia hoje); só turnos da MESMA empresa disputam o lock, e o
  objetivo é exatamente serializá-los (I-8). *(QUO-03; AGENTS.md concorrência)*
- **SQLite vs Postgres na serialização:** no SQLite `FOR UPDATE` é no-op do driver;
  a prova da corrida real é executada no Postgres da matriz de dialetos (CI). No
  SQLite os testes provam a semântica (resolução de quota, bloqueio por soma), não
  a contenção física. *(QUO-03; L-038)*
- **`FakeChatModel` com shape novo:** trocar `with_structured_output` para
  `include_raw=True` muda o contrato usado por TODOS os testes de grafo — o update
  do `conftest.py` é pré-requisito do primeiro PR (T1), nunca um follow-up.
  *(AGENTS.md Testes)*
- **Índice funcional em `user`:** `op.create_index` com expressão `lower(email)` não
  é gerado por autogenerate — migração escrita à mão (padrão do repo). No Postgres,
  `CREATE UNIQUE INDEX` fora de `CONCURRENTLY` trava escrita na tabela `user`
  durante a janela de deploy; aceito (tabela pequena, janela curta) e documentado
  no ADR. *(IDT-02)*
- **Duplicatas pré-existentes:** migrações 2 e 5 são fail-fast — um ambiente com
  duplicatas não migra até resolução manual. Procedimento de resolução fica no ADR
  de cada task (decisão humana 4). *(IDT-02; HST-02)*
- **Heurística fail-closed pode bloquear deploy legítimo** (host não-local com
  segredo dev intencional): intencional — fail-closed (I-13). O operador corrige
  definindo `AUTH_SECRET`; mensagem de erro orienta. *(CFG-02)*
- **`SecretStr` rompe consumidores de `str`:** `auth/backend.py` e `auth/manager.py`
  precisam `.get_secret_value()`; `ChatOpenAI` aceita `SecretStr` nativamente.
  Espalhamento coberto por busca de `auth_secret`/`llm_api_key` no repositório
  (8 ocorrências mapeadas). *(CFG-04)*
- **Purga de `Convite.email` vs auditoria:** a linha é mantida com e-mail vazio — o
  `token_hash` de convites expirados já é inaceitável, e o histórico de criação
  permanece auditável sem o dado pessoal. *(PII-02)*
- **Timezone:** `uso_no_mes`/`purgar_expiradas` continuam exigindo `datetime` aware
  (padrão AD-019/AD-022); as novas rotinas de purga de convite reusam o mesmo
  `agora` aware. *(PII-02; L-031)*
- **Ordem das regexes de PII:** telefone/documento compartilham dígitos pontuados —
  a ordem fixada (e-mail → CNPJ → CPF → telefone → endereço → CEP → nome) é
  provada por teste discriminante por categoria. *(PII-01)*

## Open Questions

None. Todas as decisões de produto foram tomadas no Checkpoint 1 (8 decisões
vinculantes); as decisões técnicas remanescentes (mecânica do lock, índice
funcional vs coluna normalizada, parsing de fontes, heurística de produção) estão
justificadas em `design.md` §"Decisões técnicas".

## Success Criteria

- [ ] Um turno só-supervisor registra `tokens_usados > 0` e o registro por empresa
      reflete supervisor + especialistas (C-1 fechado).
- [ ] Corrida de quota em Postgres de teste: exatamente um vencedor, soma dentro da
      quota, empresa B nunca bloqueada pela A (I-8 fechado).
- [ ] Sem `usage_metadata`, nenhuma contagem é 0 para texto não vazio (I-7 fechado).
- [ ] `Ana@X.COM ` e `ana@x.com` são a mesma identidade; índice único provado nos
      dois dialetos (I-1 fechado).
- [ ] `/cadastro` responde 429 na rajada (I-2 fechado).
- [ ] Convidar e-mail registrado devolve resposta idêntica; conflito só no log
      (I-3 fechado).
- [ ] Toda conta nasce `is_verified=False` sem quebrar login/rotas (I-4 fechado).
- [ ] E-mail/CPF/CNPJ redigidos antes do LLM e no histórico (I-5 fechado).
- [ ] `Convite.email` purgado em expirado/usado (I-10 fechado).
- [ ] `retention_days <= 0`: purga recusada + erro logado + CheckConstraint +
      validação no repositório (I-11 fechado).
- [ ] Marcador `Fontes:` de dado importado não interpretado; fontes persistidas
      batem com as tools do turno (I-6 fechado).
- [ ] `conversation` com constraint única, upgrade/downgrade provados, corrida
      tolerada (I-9 fechado).
- [ ] `llm_timeout_s`/`llm_max_retries` aplicados ao `ChatOpenAI` (I-12 fechado).
- [ ] Config fail-closed: segredo dev barrado com host externo independente de
      `AMBIENTE`; sqlite barrado em prod; segredos `SecretStr` (I-13 fechado).
- [ ] Gate do repo verde nos dois dialetos: `black --check`, `ruff check`,
      `pytest` (cobertura ≥ 80%).
