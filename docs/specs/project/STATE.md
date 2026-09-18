# State

**Last Updated:** 2026-09-17
**Current Work:** F1 (MVP) — branch de integração `feat/f1-mvp` (@ `5bcac81`);
T1–T23 + T34 concluídos (24 de 34), T24 (redação de PII) é a próxima.
Fluxo épico + 1 PR por task com CI (AD-016). Detalhe por task em
`docs/specs/features/f1-mvp/tasks.md` e no handoff `.opencode/CONTEXT.md`.

---

## Recent Decisions (Last 60 days)

### AD-001: Produto SaaS multi-cliente, web, para PMEs de logística (2026-09-11)

**Decision:** gestlog é SaaS multi-cliente, acessado por app web com chat; ICP =
transportadoras/operadores PME sem TI próprio; idiom pt-BR.
**Reason:** é a dor validada (dados dispersos em planilha) e o formato do código
atual (supervisor + especialistas conversacionais).
**Trade-off:** SaaS traz tenancy, auth e LGPD para o MVP, aumentando o escopo.
**Impact:** F1 precisa de conta por empresa, login e isolamento por `tenant_id`.

### AD-002: Copiloto read-only no MVP; escrita só na F2 via HITL (2026-09-11)

**Decision:** no MVP o gestlog apenas recomenda e explica; nenhuma escrita nos
sistemas de origem. Escrita entra na F2 com aprovação humana.
**Reason:** segurança e prazo; a dor de cadastros incompletos exige correção, mas
o valor da escrita só se justifica depois do núcleo read validado.
**Trade-off:** adia o valor de correção (F2) em troca de um MVP seguro.
**Impact:** todos os requisitos do MVP são de leitura; a arquitetura HITL fica
desenhada para a F2.

### AD-003: Dados por importação agora, conectores de API depois (2026-09-11)

**Decision:** MVP importa CSV/planilha; integrações de API por tenant são a F3.
**Reason:** entrega valor sem depender de cada TMS/ERP/WMS do cliente.
**Trade-off:** dados não são em tempo real no MVP.
**Impact:** F1 inclui ingestão com validação; F3 substitui/complementa.

### AD-004: LLM hospedado pela plataforma, medido por tenant (2026-09-11)

**Decision:** a plataforma hospeda e paga o LLM (endpoint OpenAI-compatível) e
mede uso por tenant; BYO-LLM/on-prem fica para a F5.
**Reason:** simplicidade de onboarding e controle de custo/experiência.
**Trade-off:** custo de LLM vira custo da plataforma; exige quotas (FR-14).
**Impact:** NFR-07 e FR-14 no MVP.

### AD-005: LGPD sério com redação de PII antes do LLM (2026-09-11)

**Decision:** PII de clientes é tratada; minimizada/redigida antes de ir ao LLM;
retenção configurável; sem treino em dados do cliente; provedor com
DPA/zero-retention.
**Reason:** PII está no escopo (destinatários) e o LLM é de terceiros.
**Trade-off:** redação adiciona complexidade à pipeline.
**Impact:** NFR-05 e requisito de auditoria por tenant.

### AD-006: Roadmap por fases sem datas; execução solo (2026-09-11)

**Decision:** fases M1–M5 sem calendário; critérios de saída por fase.
**Reason:** execução individual.
**Trade-off:** menos previsibilidade de datas externa.
**Impact:** planejamento guiado por `docs/specs/project/ROADMAP.md`.

### AD-007: Stack da F1 (FastAPI + Jinja/HTMX + Postgres + FastAPI Users) (2026-09-11)

**Decision:** backend FastAPI; UI SSR com Jinja2 + HTMX + SSE; Postgres único com
`tenant_id`; autenticação self-hosted com FastAPI Users; copiloto reaproveita o
grafo LangGraph existente.
**Reason:** máxima reutilização do core Python/LangGraph, mínimo de peças para dev
solo, isolamento por tenant simples e padrão de mercado.
**Trade-off:** SSR/HTMX é menos flexível que uma SPA; migrar para SPA depois custa.
**Impact:** tasks T1–T33 em `docs/specs/features/f1-mvp/tasks.md` seguem esse stack.

### AD-008: Nomenclatura — Empresa (tenant) em português (2026-09-11)

**Decision:** no código, usar `Empresa`/`empresa_id` (modelo, tabela e colunas) em
vez de `Tenant`/`tenant_id`, seguindo a convenção de nomes em português do `AGENTS.md`.
**Reason:** consistência com o restante do código (tools, repositórios, docstrings).
**Trade-off:** afasta do vocabulário SaaS em inglês; docs mantêm "tenant" entre parênteses.
**Impact:** migration inicial regenerada com tabela `empresa`; AD-007 e specs usam
"tenant" como termo de domínio, "Empresa" como nome de código.

### AD-009: Catálogo de ferramentas da F1 (2026-09-11)

**Decision:** formalizar um "Catálogo de ferramentas (F1)" no `design.md` antes da
Fase 5, com 4 tools read-only novas (`listar_entregas_atrasadas`,
`comparar_fornecedores`, `listar_abaixo_minimo`, `dias_de_cobertura`) além das 9
existentes. Tools de cadastros (read/sugerir) e de escrita (HITL) ficam para a F2.
**Reason:** os agentes precisam de tools de busca e comparação para recomendar nos
4 domínios; decidir capacidade é papel do design, não do Execute.
**Trade-off:** exige tabelas de apoio (movimentações de estoque, histórico de
fornecedor, datas de previsão/entrega no transporte).
**Impact:** adicionar tasks ao `tasks.md` da F1. **Pendente:** o usuário indicou que
tem tools próprias a incluir — capturar antes de fechar o catálogo.
**Status:** ✅ resolvida em 2026-09-12 pela AD-010; as 4 tools provisórias foram
substituídas por tools nomeadas (mapeamento no `design.md`).

### AD-010: Inventário real de tools do usuário (2026-09-12)

**Decision:** adotar como catálogo canônico no `design.md` o inventário fornecido
pelo usuário — 1 tool comum (`enviar_resposta_logistica`) + tools por domínio
(estoque, transporte, fornecedores). A F1 implementa **apenas leitura/análise**;
as de **escrita/ação** ficam registradas para a F2 com HITL. Nomes em português
(AD-008). As 4 tools provisórias da AD-009 foram substituídas por tools nomeadas.
Nova task **T34** (tool comum); T14–T16 ampliadas.
**Reason:** o usuário especificou as tools dos especialistas; a F1 é read-only
(AD-002), então só entram leitura/análise.
**Trade-off:** exige tabelas de apoio para análise (movimentações, histórico) e a
tool comum altera o binding de tools dos três especialistas.
**Impact:** `design.md` §"Catálogo de ferramentas (F1)"; `tasks.md` T14–T16 + T34;
T17 passa a depender de T34.

### AD-011: Docs-as-code — documentação em `docs/`, versionada (2026-09-12)

**Decision:** isolar o contexto conceitual do código executável: specs/planejamento
passam de `.specs/` para `docs/specs/` (ao lado de `docs/business/`), e `docs/` é
**versionado** no git. Nada de docs em `.gitignore`. Referências atualizadas em
`docs/` e no scaffold `.opencode/`.
**Reason:** organização docs-as-code; docs e código vivem no mesmo repo, mas em
árvores separadas e revisáveis.
**Trade-off:** commits passam a misturar código e documentação; sem impacto técnico.
**Impact:** estrutura macro do repo = `src/` (executável) + `docs/` (conceitual) +
`tests/`; `.specs/` deixa de existir.

### AD-012: Pacote único com fronteiras conceituais (não monorepo) (2026-09-12)

**Decision:** manter um **único pacote** (`src/gestlog/`) no F1, organizado em três
fronteiras conceituais: `apps` (entrada/deploy: `cli.py`, `web/`, `auth/`,
`copilot/`), `agents` (grafo e domínio: `graph.py`, `state.py`, `agents/`, `tools/`)
e `libs` (fundação: `config.py`, `llm.py`, `db/`, `repositories/`). Direção de
dependência `apps → agents → libs` (+ `apps → libs`), nunca invertida. `db/` +
`repositories/` são a única porta de SQL.
**Reason:** driver é **clareza**, não deploy independente. O gestlog é um único
deployable e o multiagente roda in-process (nós do LangGraph, não serviços). Um
monorepo multi-pacote traria workspace uv, múltiplos `pyproject`, tooling de
fronteiras e refatoração de T1–T5 sem consumidor que justifique.
**Trade-off:** fronteiras são convenção (não impostas por ferramenta); exige
disciplina de imports.
**Impact:** `AGENTS.md` §"Estrutura e fronteiras" vira a fonte de verdade de onde
cada coisa mora. **Gatilho de migração:** extrair para pacotes só quando houver
deploy/escala independentes (ex.: worker de alertas da F4 ou UI como app próprio),
de forma incremental (`libs/*` → `agents/` → `apps/`).

### AD-013: Camada async isolada para o auth (FastAPI Users) (2026-09-12)

**Decision:** o FastAPI Users 15 só oferece `SQLAlchemyUserDatabase` com
`AsyncSession`. Adicionar `build_async_engine`/`build_async_session_factory`/
`init_async_db` em `libs/db` e concentrar o uso de `AsyncSession` na camada de auth
(`auth/db.py`). Repositórios e copilot seguem **sync**. `aiosqlite` entra como dep
de dev (testes); em produção o engine async usa o mesmo `DATABASE_URL`
(`postgresql+psycopg`).
**Reason:** menor custo que refatorar T3–T5 para async, mantendo FastAPI Users
nativo.
**Trade-off:** duas camadas de sessão (sync + async) e dois pools na mesma app.
**Impact:** T6; `config.py` ganha `auth_cookie_name`/`auth_cookie_secure`;
`AGENTS.md` §"Estrutura e fronteiras" (libs sync, apps pode async).

### AD-014: `AMBIENTE=prod` exige `AUTH_SECRET` forte (2026-09-13)

**Decision:** `config.py` ganha `ambiente` (`dev`|`prod`). Em `prod`, a
inicialização falha se `auth_secret` for o placeholder de dev
(`dev-secret-change-me`) ou tiver menos de 32 caracteres. Em `dev` o placeholder
continua valendo.
**Reason:** code review do PR #2 (CRITICAL) — JWT assinado com segredo público
permitiria forjar qualquer sessão (inclusive admin) em produção.
**Trade-off:** exige configurar `AUTH_SECRET`/`AMBIENTE` no deploy; sem custo em dev.
**Impact:** `config.py` (`SEGREDO_DEV`, `TAMANHO_MINIMO_SEGREDO`, validador),
`.env.example`, testes de config.

### AD-015: Hardening de auth adiado (rate limiting e convite por token) (2026-09-13)

**Decision:** no MVP, `/auth/login`, `/onboarding` e `/empresa/convites` ficam sem
rate limiting e o convite continua recebendo a senha do usuário pelo admin.
**Reason:** rate limiting confiável exige estado compartilhado (Redis) ou desenho
multi-worker, e convite por token exige envio de e-mail — ambos fora do escopo F1.
**Trade-off:** aceita risco de brute-force/abuso e de o admin conhecer a senha do
convidado até o hardening.
**Impact:** capturado em Deferred Ideas; revisar antes de abrir o produto ao público.

### AD-016: Fluxo épico + 1 PR por task com CI obrigatório (2026-09-13)

**Decision:** tratar a F1 como produto maduro: `feat/f1-mvp` é a branch de
integração do épico; cada task T10–T34 vira uma branch curta
(`feat/f1-tXX-<slug>`) com PR contra a integração, `tasks.md` + testes no mesmo
PR, CI verde (`black --check`, `ruff check`, `pytest`) e code review antes do
squash-merge. `main` só recebe a F1 no PR de release + tag `v0.1.0`. Proibido
`force-push` em branch compartilhada.
**Reason:** 34 tasks exigem histórico versionado e rastreável; o modelo anterior
(branch longa + stacked + force-push) não é aceitável para produto maduro.
**Trade-off:** mais overhead por task (branch/PR/review) e `main` fica atrás até o
release da F1.
**Impact:** `.github/workflows/ci.yml` (novo); `AGENTS.md` §"Fluxo da feature
(épico + task)"; PRs stacked #1/#2/#3 aposentados.

### AD-017: Recomendação estruturada por passo terminal da tool comum (2026-09-17)

**Decision:** a resposta do copiloto é estruturada como uma `Recomendacao`
(`dominio`, `texto`, `justificativa`, `fontes`, `insuficiente`) extraída do
**passo terminal** do especialista: `create_specialist_node` detecta a chamada a
`enviar_resposta_logistica` (só quando é a única do passo), executa a tool e
devolve o texto composto como resposta final, registrando `dominio` no
`AgentState`. O `CopilotService` converte a string `fontes` em `list[str]`,
persiste `Recommendation` apenas quando há base e responde com
`MENSAGEM_INSUFICIENCIA` quando não há fonte. A tool comum ganhou
`justificativa: str = ""` (extensão retrocompatível do contrato da T34).
**Reason:** COP-03/COP-04 (recomendação + justificativa + fonte; aviso de dado
insuficiente) sem uma segunda chamada ao LLM — que dobraria custo/latência e
reintroduziria risco de alucinação no ponto que deve ancorar confiança. O schema
de function calling já obriga `resposta` e dá `default: ""` a
`fontes`/`justificativa`, tornando a ausência de fonte um sinal confiável.
**Trade-off:** o parser lê o formato textual escrito pela própria tool (rótulos
compartilhados em `tools/common.py`), acoplando leitura e escrita; "sem fonte ⇒
insuficiência" substitui a pergunta de esclarecimento do especialista (COP-02
AC3) por uma mensagem genérica; `answer()` devolve o texto composto cru no
caminho feliz (apresentação limpa é a T23).
**Impact:** `state.py` (`dominio`), `agents/base.py`, `tools/common.py`,
`copilot/service.py` e prompts dos 3 especialistas; ADR
`docs/adr/t21-recomendacao-fontes-insuficiencia-self-review.md`; T22/T23 reusam a
`Recommendation` persistida. Débito: distinguir "sem base" de "preciso de um dado
do usuário" (T25/T29).

### AD-018: Feedback de recomendação escopado por empresa + usuário, append-only (2026-09-17)

**Decision:** o aceite/descarte é registrado por `POST /recomendacoes/{id}/feedback`
(corpo `form` com `decisao` em `{aceita, descartada}`). A autorização precede a
escrita: `RecommendationRepository.get_do_usuario` só devolve a recomendação se a
conversa pertencer ao **mesmo `empresa_id` e `user_id`** da sessão; caso contrário
a rota responde **404** (sem revelar existência). O `Feedback` grava o
`user_id` atuante e `created_at`; o histórico é **append-only** (sem upsert), e
consumidores de KPI usam a **última** decisão por recomendação.
**Reason:** COP-06 pede a decisão com usuário, tenant e timestamp, e a conversa já é
por (empresa, usuário) desde a T20 — decidir a própria recomendação é a autoria
natural. O 404 (em vez de 403) segue `verificar_empresa_do_recurso` e evita um
oráculo de existência entre tenants.
**Trade-off:** decisões repetidas coexistem (um `COUNT(*)` ingênuo contaria a
troca); um upsert/idempotência ficaria para quando a UI (T23) estabilizar o botão.
O corpo em `form` (não JSON) casa com o HTMX da T23.
**Impact:** `repositories/conversations.py` (`get_do_usuario`,
`list_by_recommendation`), `web/feedback.py` (novo), `web/app.py`,
`web/schemas.py` (`DecisaoFeedback`); ADR
`docs/adr/t22-feedback-aceitar-descartar-self-review.md`; T23 (botões) e T32 (KPIs
agregando a última decisão) reusam o endpoint.

### AD-019: Feedback na UI por pareamento na leitura (sem migration) (2026-09-17)

**Decision:** a UI da T23 exibe fontes + botões aceitar/descartar por turno sem
criar vínculo no banco. O read-model `Turno` ganhou `recomendacao_id`, `fontes` e
`decisao`; `_montar_turnos` intercala mensagens e recomendações por
`(created_at, tipo, id)`, com o `tipo` (mensagem=0 antes de recomendação=1) à
frente do `id` para resolver empates de timestamp de forma determinística (o `id`
é UUID aleatório e não representa ordem). A decisão vigente vem de
`FeedbackRepository.latest_by_conversation` (append-only, última vence) e o
endpoint da T22 passou a devolver um **fragmento HTML** (Jinja autoescape) para o
swap HTMX sem recarregar.
**Reason:** a T21 persistiu a `Recommendation` apenas ligada à conversa; para não
introduzir migration nem mudar o schema da T20/T21, o pareamento é derivado na
leitura a partir da ordem cronológica de escrita (a recomendação é gravada logo
após a resposta).
**Trade-off:** o pareamento depende dos timestamps do servidor; empates são
tratados por `tipo`, mas *clock skew*/edição manual continuam fora de garantia
(mesma limitação de ordenação já registrada na T20). O turno ao vivo (SSE) ainda
não recebe botões — a decisão aparece ao recarregar o histórico; emitir um
`event: fontes`/fragmento no SSE fica para task futura.
**Impact:** `copilot/service.py` (`Turno`/`_montar_turnos`/`carregar_historico`),
`repositories/conversations.py` (`latest_by_conversation`), `web/feedback.py`
(fragmento), `web/templates/{chat,_feedback}.html`, `web/static/app.css`; ADR
`docs/adr/t23-feedback-ui-self-review.md`.

### AD-020: Redação de PII por regex + allowlist, determinística e sem LLM (2026-09-18)

**Decision:** a T24 introduz `src/gestlog/privacy/` com `redact(texto, politica) ->
RedactedText`, que substitui telefones (`[TELEFONE]`), endereços/CEP (`[ENDERECO]`)
e nomes comuns (`[NOME]`) por marcadores. A política é um `PoliticaRedacao` frozen
(allowlist `NOMES_COMUNS` + marcadores, trocável por tenant); nomes são casados
pela forma acentuada **e** pela forma sem diacríticos (NFKD), e a substituição
escapa `\` para o marcador ser sempre literal no `re.sub`. O original não é
guardado: `RedactedText` devolve só `texto` minimizado + `categorias` encontradas.
**Reason:** o design da F1 (`design.md`, "PII Redaction") exige regex/allowlist
sem LLM — redação barata, offline e reproduzível, adequada ao MVP em que a PII de
clientes não pode sair para o provedor do modelo. Não há dependência de
apps/agents (fronteira `libs`).
**Trade-off:** a heurística sobre-redige (ex.: "São Paulo" contém o prenome
"Paulo") e não cobre nomes fora da allowlist; o falso positivo é o erro seguro
para privacidade. Endereço exige prefixo+numero e nomes exigem forma capitalizada.
**Impact:** `src/gestlog/privacy/{__init__,politica,redacao}.py`,
`tests/privacy/test_redacao.py`; ADR `docs/adr/t24-redacao-pii-self-review.md`.
A integração no copiloto (preservando o texto original para a UI) é a **T25**.

### AD-021: PII redigida antes do LLM e no histórico; original não circula (2026-09-18)

**Decision:** a T25 integra a redação da T24 no `CopilotService.answer`: a pergunta
do usuário passa por `redact(...)` antes de `run_query`, e a **versão redigida** é
tanto enviada ao LLM quanto gravada em `Message.conteudo_redigido` via
`registrar_turno`; o texto original não é enviado ao provedor nem persistido. A UI
ao vivo continua exibindo o original (ele chega pelo query param de `/chat/pergunta`),
e o histórico passa a mostrar os marcadores (`[NOME]`/`[ENDERECO]`/`[TELEFONE]`).
**Reason:** SEC-01 exige que PII não saia para o provedor; SEC-03/retenção pede
minimizar o que é armazenado. Persistir a versão redigida alinha o nome do campo
`conteudo_redigido` e a intenção já registrada na ADR da T20 ("a redação de PII
passa a agir sobre o `conteudo_redigido`").
**Trade-off:** após recarregar o histórico, a pergunta aparece com marcadores em vez
do texto literal — perda de fidelidade aceita em troca de não reter PII. O teste do
*Done when* inspeciona as mensagens efetivamente entregues ao modelo (fake ganhou
`mensagens_recebidas`), não apenas o registro persistido.
**Impact:** `copilot/service.py` (`answer`), `tests/conftest.py` (captura do prompt
no fake), `tests/copilot/test_service.py`; ADR
`docs/adr/t25-integrar-pii-self-review.md`. Medição de uso/quota fica na **T27/T28**.

### AD-022: Auditoria por catálogo validado e retenção por empresa (2026-09-18)

**Decision:** a T26 cria `src/gestlog/audit/` com um catálogo de eventos
(`EVENTO_PERGUNTA`, `EVENTO_RECOMENDACAO`, `EVENTO_FEEDBACK`, `EVENTO_IMPORTACAO`)
e `registrar_evento(...)`, que valida o nome do evento e delega ao `AuditRepository`
**sem commit** — o commit fica com a unidade de trabalho da interação. O
`CopilotService.answer` registra `pergunta` (detalhe `{dominio, pii: categorias
redigidas}` — nunca o valor) e `recomendacao` (`{dominio, fontes}`) na mesma
transação do turno. A retenção é por empresa: `retencao_dias(empresa, settings)`
usa `Empresa.retention_days` ou cai para `Settings.default_retention_days`;
`purgar_expiradas` itera as empresas e apaga conversas vencidas e seus dependentes
(feedback → recommendation → message → conversation).
**Reason:** SEC-02 pede trilha de auditoria por tenant em interações relevantes;
SEC-03 pede respeitar o prazo de retenção. Registrar metadados (domínio, fontes,
categorias de PII encontradas) dá visibilidade sem duplicar o dado sensível.
O SQL de deleção fica em `repositories/` (única porta de banco), mantendo `audit/`
como orquestração — e a ordem de FK evita órfãos.
**Trade-off:** a purga é uma operação explícita (chamável por um job/cron), não um
agendador embutido; `UsageRecord` (agregado de custo) e o próprio `AuditLog`
(trilha) não são purgados por essa política. Feedback e importação ainda não
chamam a auditoria (wiring fora do escopo acordado); `agora` naive é rejeitado
para não deslocar o corte entre SQLite/Postgres.
**Impact:** `src/gestlog/audit/{eventos,retencao}.py`, `repositories/empresas.py`
(`list_all`), `repositories/conversations.py` (`purgar_expiradas`),
`copilot/service.py` (`_registrar_auditoria`), `tests/audit/test_auditoria.py`,
`tests/copilot/test_service.py`; ADR `docs/adr/t26-auditoria-retencao-self-review.md`.

### AD-023: Quota mensal medida por empresa e bloqueio pré-chamada (2026-09-18)

**Decision:** a T27 cria `src/gestlog/copilot/metering.py` com `record_usage`
(registra tokens/modelo por empresa, sem commit) e `check_quota`, que soma o uso
do **mês corrente** (`_inicio_do_mes` + `UsageRepository.total_tokens_desde`) e
levanta `QuotaExcedida(empresa_id, usado, quota)` quando o uso atinge
`Settings.llm_monthly_token_quota`. `Settings` é a fonte do teto; a soma all-time
(`total_tokens`) permanece para KPIs.
**Reason:** QUA-02 pede atribuir uso ao tenant e bloquear ao estourar a quota. A
janela mensal evita que o consumo histórico bloqueie para sempre o tenant. O
registro sem commit mantém a telemetria na mesma unidade de trabalho da chamada
(o copiloto integra isso na T28).
**Trade-off:** o bloqueio é pré-chamada e *best-effort*: só se sabe o custo real
**depois** da resposta; um tenant pode ultrapassar a quota na última chamada
permitida. Bloquear em `>=` é conservador (teto de gasto). O erro é tipado para a
T28 traduzir em mensagem clara sem derrubar a sessão.
**Impact:** `src/gestlog/copilot/metering.py`, `repositories/telemetry.py`
(`total_tokens_desde`), `copilot/__init__.py` (reexports),
`tests/copilot/test_metering.py`; ADR `docs/adr/t27-uso-quota-self-review.md`.

### AD-024: Uso medido no estado do grafo e quota bloqueada sem exceção (2026-09-18)

**Decision:** a T28 liga a medição da T27 ao copiloto. `AgentState` ganhou
`tokens_usados` (reducer `operator.add`), acumulado pelo nó especialista a partir
do `usage_metadata` de cada chamada ao modelo (o nó só devolve a resposta final,
descartando as mensagens intermediárias, então ler `state["messages"]` no serviço
perderia tokens). `CopilotService.answer` chama `check_quota` antes de qualquer
chamada; ao estourar, devolve `MENSAGEM_QUOTA_EXCEDIDA` sem invocar o LLM nem
persistir turno. Depois do grafo, registra `record_usage(..., tokens_usados)`
antes de `registrar_turno`, na mesma transação.
**Reason:** QUA-02 pede medir cada chamada e bloquear de forma que a sessão não
caia. Devolver a mensagem como parte do fluxo (em vez de deixar `QuotaExcedida`
vazar para a rota) mantém a UX previsível e o SSE da T18 intacto. Ancorar o
acumulador no estado preserva a arquitetura "só a resposta final sobe" da T21.
**Trade-off:** os tokens do supervisor (roteamento via `with_structured_output`)
não entram na soma — a medição cobre a geração dos especialistas. O bloqueio é
pré-chamada e best-effort: só se sabe o custo depois da resposta. Modelos que não
reportam `usage_metadata` contam 0.
**Impact:** `state.py` (`tokens_usados`), `agents/base.py` (`_tokens_da_resposta`,
acumulação e `SpecialistOutput`), `copilot/service.py` (`answer`),
`copilot/__init__.py` (reexport), `tests/conftest.py` (fake com tokens),
`tests/copilot/test_service.py`; ADR
`docs/adr/t28-integracao-uso-quota-self-review.md`.

### AD-025: Golden set declarativo e runner com métricas de qualidade (2026-09-18)

**Decision:** a T29 cria `src/gestlog/evaluation/golden.py` com o formato do golden
set (`CasoGolden`: id, pergunta, domínio, fontes esperadas, requer recomendação),
carregamento validado de JSON (`carregar_golden_set`) e o runner
`run_golden_set(casos, model, settings)` que compila o grafo e, por caso, reusa
`extrair_recomendacao` (T21) para medir **acurácia** (recomendação/insuficiência e
domínio esperados), **alucinação** (recomendar quando o caso não pedia base) e
**fonte correta** (fontes esperadas presentes). `RelatorioAvaliacao` agrega tudo
com taxas protegidas de divisão por zero. `evals/golden_set.json` é o
dataset-semente; o script real contra o modelo fica na T30.
**Reason:** QUA-01 pede medir qualidade por domínio. Separar o dado (JSON) do
código permite evoluir o conjunto sem tocar no runner e mantém o núcleo testável
com o modelo fake do `conftest` (grafo real, modelo injetado). Reusar a extração
da T21 evita divergir do que o runtime realmente entrega.
**Trade-off:** `evaluation` depende de `copilot` (reuso de `extrair_recomendacao`
e de `texto_resposta`, agora público) — mover o parser para `agents` seria um
refactor maior. Tokens do supervisor e redação de PII não entram na avaliação; a
`fonte_correta` exige as fontes esperadas, sem penalizar fontes extras.
**Impact:** `src/gestlog/evaluation/{__init__,golden}.py`, `evals/golden_set.json`,
`copilot/service.py` (`texto_resposta` público), `copilot/__init__.py`,
`tests/evaluation/test_golden.py`; ADR `docs/adr/t29-golden-set-self-review.md`.

### AD-026: Script de avaliação com lógica testável e launcher fino (2026-09-18)

**Decision:** a T30 separa a lógica do script em `gestlog.evaluation.script`
(`gerar_relatorio` com modelo injetável, `salvar_relatorio` e `main`), deixando
`evals/run_golden_set.py` como launcher fino. `relatorio.py` agrega
`acuracia_por_dominio` (casos sem domínio viram `fora_de_escopo`) e serializa o
relatório em JSON. O default de `gerar_relatorio` constrói o modelo real via
`build_chat_model`; nos testes injeta-se o fake. O relatório é gravado em
`evals/relatorio.json`, artefato gerado e ignorado no git.
**Reason:** QUA-01 pede gerar o relatório a partir do golden set real. Manter a
lógica dentro do pacote (testável, coberta) e só o disparo em `evals/` permite
provar o comportamento com fake sem rede, deixando a operação manual (um comando)
fora da suíte. Caminhos derivados de `__file__` não dependem do cwd.
**Trade-off:** o script é uma operação manual, não agendada; a acurácia por
domínio considera a expectativa do caso (não a rota obtida) e `main` fica com
`# pragma: no cover`. O relatório gerado não é versionado.
**Impact:** `src/gestlog/evaluation/{relatorio,script}.py`, `evaluation/__init__.py`,
`evals/run_golden_set.py`, `.gitignore`, `tests/evaluation/test_script.py`; ADR
`docs/adr/t30-script-avaliacao-self-review.md`.

### AD-027: Gestão de usuários/papéis pelo admin, com proteção do último admin (2026-09-18)

**Decision:** a T31 adiciona `GET/PATCH/DELETE /empresa/usuarios[/{id}]` em
`web/admin.py`, todas sob `exigir_papel("admin")` (T8), com os casos de uso em
`auth/accounts.py` (`listar_usuarios`, `alterar_papel`, `remover_usuario`).
O alvo é sempre resolvido por `(empresa_id, user_id)` da sessão: outra empresa
resulta em **404** (sem vazar existência). Rebaixar ou remover o **último admin**
da empresa é bloqueado com **409**. A remoção apaga o `Membership`, então
`get_current_membership` deixa de resolver e o acesso cai (**403**) — é o que
"remoção revoga acesso" exige.
**Reason:** ADM-01 pede que o admin altere papel e remova usuários do tenant. Reusar
`exigir_papel` mantém uma única porta de autorização, e a regra do último admin
evita deixar a empresa órfã de quem gerencie usuários.
**Trade-off:** `Membership.user_id` (`Uuid`) e `User.id` (`GUID` do FastAPI Users)
serializam diferente no SQLite, então o `JOIN` direto retorna vazio; `listar_usuarios`
contorna com `User.id.in_(ids)` (débito: alinhar os tipos exige migration). Os
eventos de gestão ainda não chamam a auditoria da T26 (fora do escopo).
**Impact:** `auth/accounts.py`, `web/admin.py`, `web/schemas.py` (`PapelAtualizar`),
`web/app.py`, `tests/auth/test_admin.py`; ADR `docs/adr/t31-admin-papeis-self-review.md`.

### AD-028: Dashboard de KPIs por empresa e período, com decisão vigente (2026-09-18)

**Decision:** a T32 cria `repositories/kpis.py` com `KpiRepository.resumo(empresa_id,
desde, ate) -> ResumoKpis`, agregando **adoção** (conversas, perguntas,
recomendações), **aceitação** (decisão vigente "última vence", reusando a semântica
append-only da T22) e **cobertura de dados** (snapshot de itens de estoque,
fornecedores e registros de transporte). A página `GET /kpis` (guard admin/gestor)
converte `desde`/`ate` (data) em limites UTC inclusivos e renderiza `kpis.html`.
**Reason:** KPI-01 pede que o gestor veja os indicadores do tenant no período. As
agregações vivem no repositório (SQL confinado, isolamento por `empresa_id`), e a
aceitação usa a decisão vigente para refletir a intenção atual, não o total de
cliques. A cobertura é o retrato atual dos dados importados (não tem `created_at`).
**Trade-off:** a decisão vigente ordena por `(Feedback.created_at, Feedback.id)`;
como o `id` é UUID aleatório, empates de timestamp têm desempate não determinístico
(mesmo padrão da T20/T23; cliques reais têm tempos distintos). Corrigir exigiria uma
coluna monotônica. A cobertura ignora o período por não haver timestamp nos dados.
**Impact:** `repositories/kpis.py`, `repositories/__init__.py`, `web/kpis.py`,
`web/templates/kpis.html`, `web/templates/base.html`, `web/app.py`, `web/__init__.py`,
`tests/web/test_kpis.py`; ADR `docs/adr/t32-dashboard-kpis-self-review.md`.

---

## Active Blockers

Nenhum bloqueio ativo.

_(B-001 — repositório não era git — resolvido em 2026-09-11: `git init -b main`,
`.gitignore` atualizado, commit raiz `31c7368` e remote `origin` publicado em
https://github.com/Andreson1010/gestlog (privado).)_

---

## Lessons Learned

### L-001: Artefatos opencode devem ser agnósticos

**Context:** scaffold `.opencode/` foi copiado do projeto medasist.
**Problem:** skills e agentes vinham com paths e regras específicas do medasist.
**Solution:** generalizados para descobrir comandos/padrões via `AGENTS.md`;
especificidades do projeto ficam no `AGENTS.md`.
**Prevents:** retrabalho ao reutilizar o scaffold em outros projetos.

---

## Quick Tasks Completed

| #   | Description | Date | Commit | Status |
| --- | ----------- | ---- | ------ | ------ |
| 001 | Copiar e generalizar `.opencode/` (skills, agentes, commands) + `CONTEXT.md` | 2026-09-11 | — (sem git) | ✅ Done |
| 002 | Escrever PRD + artefatos TLC (`PROJECT`/`ROADMAP`/`STATE`) | 2026-09-11 | — (sem git) | ✅ Done |
| 003 | Inicializar git e commit raiz | 2026-09-11 | 31c7368 | ✅ Done |
| 004 | Configurar remote `origin` e publicar `main` | 2026-09-11 | 871f0be | ✅ Done |
| 005 | Planejar F1 (spec/design/tasks + TESTING) | 2026-09-11 | — | ✅ Done |
| 006 | Executar F1 Fase 1 (T1–T5) + rename `Tenant`→`Empresa` | 2026-09-11 | 8438baa | ✅ Done |
| 007 | Capturar inventário de tools e formalizar catálogo F1 (AD-010) | 2026-09-12 | — | ✅ Done |
| 008 | Reorganizar docs-as-code: `.specs/` → `docs/specs/` e versionar (AD-011) | 2026-09-12 | — | ✅ Done |
| 009 | Definir fronteiras do pacote único (AD-012) e camada async do auth (AD-013) | 2026-09-12 | — | ✅ Done |
| 010 | Executar F1 Fase 2 — T6 login/logout por cookie (FastAPI Users) | 2026-09-12 | — | ✅ Done |
| 011 | Executar F1 Fase 2 — T7 tenancy, `get_current_empresa` e guards | 2026-09-12 | — | ✅ Done |
| 012 | Executar F1 Fase 2 — T8 onboarding da conta e convites | 2026-09-12 | — | ✅ Done |
| 013 | Executar F1 Fase 3 — T9 app factory + layout Jinja/HTMX | 2026-09-12 | — | ✅ Done |
| 014 | Abrir PRs incrementais stacked (#1 Fase 1, #2 Fase 2, #3 Fase 3 draft) | 2026-09-12 | — | ✅ Done |
| 015 | Code review dos 3 PRs + correções (segredo/prod, tenancy determinística, onboarding atômico) | 2026-09-13 | — | ✅ Done |
| 016 | CI (GitHub Actions) + fluxo épico/task (AD-016; PRs #4 e #5) | 2026-09-13 | — | ✅ Done |
| 017 | Executar F1 — T10 home autenticada + redirect ao login (PR por task) | 2026-09-13 | — | ✅ Done |
| 018 | Executar F1 — T11 parsers/validadores de importação (CSV/XLSX) | 2026-09-13 | — | ✅ Done |
| 019 | Executar F1 — T12–T23 + T34 (1 PR/task, self-review + code review) | 2026-09-14…17 | `5bcac81` (T23) | ✅ Done |
| 020 | Executar F1 — T24 (redação de PII por regex + allowlist, sem LLM) | 2026-09-18 | — | ✅ Done |
| 021 | Executar F1 — T25 (integrar redação no copiloto; persistir versão redigida) | 2026-09-18 | — | ✅ Done |
| 022 | Executar F1 — T26 (auditoria por tenant + retenção configurável) | 2026-09-18 | — | ✅ Done |
| 023 | Executar F1 — T27 (medição de uso/quota mensal, bloqueio pré-chamada) | 2026-09-18 | — | ✅ Done |
| 024 | Executar F1 — T28 (medição por chamada no grafo + bloqueio de quota no copiloto) | 2026-09-18 | — | ✅ Done |
| 025 | Executar F1 — T29 (golden set: formato JSON + runner com métricas) | 2026-09-18 | — | ✅ Done |
| 026 | Executar F1 — T30 (script de avaliação: relatório JSON + acurácia por domínio) | 2026-09-18 | — | ✅ Done |
| 027 | Executar F1 — T31 (gestão de usuários/papéis pelo admin, último admin protegido) | 2026-09-18 | — | ✅ Done |
| 028 | Executar F1 — T32 (dashboard de KPIs por empresa e período) | 2026-09-18 | — | ✅ Done |

---

## Deferred Ideas

- [x] **Tools específicas do usuário** — capturadas em 2026-09-12 (AD-010) — Captured during: F1
- [x] Catálogo de tools F1 — fechado no `design.md` (AD-010); substitui as 4 provisórias da AD-009 — Captured during: F1
- [ ] Tools de escrita/ação (HITL): estoque (`gerenciar_inventario`, `gerenciar_qualidade`, `escalar_operacoes`), transporte (`organizar_envio`, `coordenar_operacoes`, `gerenciar_manuseio_especial`, `processar_devolucoes`, `gerenciar_disrupcoes`), fornecedores (`tratar_conformidade` ação) e envio externo de `enviar_resposta_logistica` — Captured during: F2
- [ ] Tools de comparação de rotas/modal — Captured during: F1/F2
- [ ] Benchmarking anonimizado entre tenants — Captured during: definição de produto
- [ ] Marketplace de conectores de terceiros — Captured during: definição de produto
- [ ] Novos domínios (contratos, devoluções, inventário) — Captured during: definição de produto
- [ ] Rate limiting em `/auth/login`, `/onboarding` e `/empresa/convites` (AD-015) — Captured during: code review F1
- [ ] Convite por token/e-mail (sem o admin definir a senha do convidado) (AD-015) — Captured during: code review F1
- [ ] Seleção de "empresa ativa" para usuários com múltiplos vínculos (hoje usa o mais antigo) — Captured during: code review F1
- [ ] Botões de aceitar/descartar no turno ao vivo (SSE), hoje só após recarregar o histórico; emitir `event: fontes`/fragmento e ordenação monotônica de mensagens (substituir o pareamento por `created_at`) (AD-019) — Captured during: F1/T23

---

## Todos

- [ ] Executar a F1 — próxima task: T33 (aceitação P1 ponta a ponta); depois o
      release `feat/f1-mvp → main` + tag `v0.1.0`.
- [ ] Ao fechar a F1: PR de release `feat/f1-mvp → main` + tag `v0.1.0`.
- [ ] Calibrar metas numéricas dos KPIs após primeiras semanas de uso.
- [ ] Débitos técnicos herdados: `UniqueConstraint(empresa_id, user_id)` em
      `conversation`, reavaliar `String(4000)`/`Text`, mover `get_sync_session`
      para `web/deps.py`, remover `TOOLS` mock do REPL quando houver banco,
      alinhar `Membership.user_id` (`Uuid`) a `User.id` (`GUID`) para permitir JOIN
      (AD-027),
      botões no turno ao vivo (SSE) e ordenação monotônica de mensagens (AD-019).
