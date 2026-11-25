# Segurança Sweep — Tasks

**Design**: `docs/specs/features/seguranca-sweep/design.md`
**Spec**: `docs/specs/features/seguranca-sweep/spec.md`
**Status**: Awaiting human approval

---

## Regras de execução (todas as tasks)

- **Branch de integração**: `feat/seguranca-sweep` acumula as 6 tasks; **1 PR por
  task** contra a integração (não contra `main`); branch de task cortada do head
  da integração, nomeada `feat/sec-tXX-<slug>` (ex.: `feat/sec-t01-quota`).
- **Migrações encadeiam** (§Migrações do design): cada PR com migração ajusta o
  `down_revision` para o head da integração no momento do corte — nunca duas
  migrações em paralelo.
- **Self-review** (`developer-self-reviewer` + ADR) antes de cada PR; **code
  review** com o `code-reviewer-agent` depois (fluxo do AGENTS.md).
- **Gate por task** (igual em todas): `uv run black --check src/ tests/ alembic/`,
  `uv run ruff check src/ tests/ alembic/`, `uv run pytest` (cobertura ≥ 80%);
  execuções focadas com `--no-cov`. Matriz de dialetos: SQLite local + Postgres no
  CI (`GESTLOG_TEST_DATABASE_URL`).
- **Testes discriminam a versão vulnerável**: cada item lista o teste cujo
  comportamento falharia no código de hoje (vermelho→verde).
- **Migrações**: upgrade **e** downgrade com 1 asserção por coluna/efeito (L-037);
  reimportar `sa`/`op` em revision gerada vazia; `make format` se editar à mão.

## Execution Plan

```
T1 (quota + migração 1 + conftest include_raw)
 └→ T2 (identidade + migração 2)
     └→ T3 (PII/LGPD + migração 3)
         └→ T5 (histórico + migração 4)
             └→ T4 (fontes — código puro, sem migração)
                 └→ T6 (config/rede — código puro, sem migração)
                     └→ ACEITA (bateria final de aceitação do épico)
```

Ordem 1→2→3→5→4→6 mantém as migrações contíguas no head da integração; T4 e T6
(só código) podem ser adiantadas sem conflito se necessário, mas os PRs NÃO
atravessam um PR de migração pendente.

---

## Task Breakdown

### T1: Quota/Metering — tokens do supervisor, estimativa, serialização (C-1, I-7, I-8)

**What**:
- [x] `agents/base.py`: `_tokens_da_resposta` → helper público `tokens_da_mensagem`
      com fallback `max(1, len(texto)//4)`; especialistas usam o helper (QUO-02).
- [x] `agents/supervisor.py`: roteador com `include_raw=True`; nó devolve
      `{"next", "tokens_usados"}` (QUO-01).
- [x] `copilot/metering.py`: `quota_da_empresa`, `travar_empresa` (FOR UPDATE +
      flush), `check_teto_global`; `check_quota` recebe a `Empresa` travada e usa a
      quota dela (QUO-03/04/05).
- [x] `copilot/service.py`: trava a empresa antes de `check_quota`; teto global
      após o check da empresa; `record_usage` no mesmo commit do turno (QUO-03/06).
- [x] `db/models.py` + migração `f1a2b3c4d5e6`: `empresa.token_quota_mensal`
      (Integer, nullable) (QUO-04).
- [x] `repositories/empresas.py::create`: valida `token_quota_mensal <= 0` →
      `ValueError` (QUO-04).
- [x] `tests/conftest.py`: `FakeChatModel.with_structured_output` devolve shape
      `{"raw", "parsed"}` (pré-requisito de todo o resto).
- [x] Testes discriminantes (ver abaixo) + ADR da task (mecânica do lock,
      salvaguarda global, janela do lock durante LLM).

**Where**: `agents/{base,supervisor}.py`, `copilot/{metering,service}.py`,
`db/models.py`, `repositories/empresas.py`, `alembic/versions/` (nova),
`tests/conftest.py`, `tests/agents/test_specialists.py`,
`tests/agents/test_supervisor.py` (ajustes de shape), `tests/copilot/test_metering.py`,
`tests/copilot/test_service.py`
**Depends on**: None · **Reuses**: reducer `tokens_usados` existente,
`QuotaExcedida`, `UsageRepository.total_tokens_desde`
**Requirement**: QUO-01..06, EDG-01/02/03/11/12 · **Tests**: unit + integration +
migration · **Gate**: completo

**Done when**:
- [x] `tests/copilot/test_metering.py::test_turno_so_supervisor_conta_tokens`
      (fake com `tokens=0` e rota FINISH direta → `tokens_usados > 0` e
      `UsageRecord` gravado) — falha no código de hoje (C-1 discriminante).
- [x] `test_tokens_sem_metadata_sao_estimados_nunca_zero` (metadata ausente e
      `total_tokens=0` → estimativa; texto não vazio nunca 0) — I-7.
- [x] `test_corrida_da_quota_tem_um_vencedor_somente` (duas sessões Postgres na
      mesma empresa; exatamente um registro por turno e soma ≤ quota) — I-8/EDG-01.
- [x] `test_empresa_b_nao_bloqueada_pela_a` (lock por linha; B responde enquanto A
      esgota) — EDG-02.
- [x] `test_quota_da_empresa_sobrepoe_o_global_e_null_cai_para_settings` — QUO-04.
- [x] `test_teto_global_bloqueia_somatorio` e
      `test_quota_estourada_devolve_mensagem_nao_500` — QUO-05/06.
- [x] Migração: coluna existe no upgrade, some no downgrade (1 asserção por efeito).
- [x] Suite completa verde no SQLite + Postgres (conftest atualizado não quebra os
      testes de grafo existentes).

---

### T2: Convite/Cadastro/Identidade (I-1..I-4)

**What**:
- [x] `auth/accounts.py`: `normalizar_email` (strip+casefold) aplicado em
      `_por_email`, `criar_conta`, `criar_convite` (IDT-01).
- [x] `auth/accounts.py::_novo_usuario`: `is_verified=False` (IDT-05).
- [x] `web/app.py`: `POST /cadastro` com `Depends(limitar("cadastro"))` (IDT-03).
- [x] `web/onboarding.py::convidar`: captura `ConviteDuplicadoError`, `logger.warning`,
      devolve 201 idêntico com token decoy (IDT-04).
- [x] `db/models.py`: `User.__table_args__` com
      `Index("uq_user_email_ci", func.lower(User.email), unique=True)`.
- [x] Migração `f2b3c4d5e6f7` (down `f1a2b3c4d5e6`): fail-fast de duplicatas
      (`GROUP BY lower(email) HAVING count(*) > 1` → `RuntimeError` listando) +
      `op.create_index` com expressão (IDT-02).
- [ ] ADR da task: procedimento de resolução manual de duplicatas de e-mail
      (fase de self-review; deve cobrir: diagnóstico das duplicatas via
      `SELECT lower(email), count(*) FROM "user" GROUP BY lower(email) HAVING
      count(*) > 1`; decisão de qual linha preservar; `UPDATE` para a forma
      canônica — strip+casefold — e reexecução do `alembic upgrade head`;
      janela de lock de escrita do `CREATE UNIQUE INDEX` no Postgres).

**Where**: `auth/accounts.py`, `web/app.py`, `web/onboarding.py`, `db/models.py`,
`alembic/versions/` (nova), `tests/auth/test_accounts.py`,
`tests/web/test_onboarding.py`, `tests/web/test_app.py` (cadastro),
`tests/test_migrations.py`
**Depends on**: T1 · **Reuses**: `RateLimiter`/`limitar`, padrão fail-fast de
migração · **Requirement**: IDT-01..05, EDG-05/06/08 · **Tests**: unit +
integration + migration · **Gate**: completo

**Done when**:
- [x] `test_email_normalizado_recusa_duplicata_por_caixa_ou_espaco`
      (`Ana@X.COM ` vs `ana@x.com` → já cadastrado; persistência normalizada) —
      falha no código de hoje (I-1 discriminante).
- [x] `test_migracao_aborta_com_duplicatas_de_email` (semear 2 e-mails case-
      divergentes → `command.upgrade` levanta listando; limpo → índice criado;
      downgrade remove; inserir duplicata case-divergente após upgrade →
      `IntegrityError` nos dois dialetos) — IDT-02/L-037.
- [x] `test_cadastro_limitado_por_janela` (n+1 POSTs → 429) — IDT-03.
- [x] `test_convidar_email_registrado_responde_como_novo_e_nao_aceita_decoy`
      (status/shape idênticos; token decoy rejeitado em `/convites/aceitar`; log
      contém o conflito) — IDT-04/EDG-06.
- [x] `test_conta_nasce_is_verified_false` (cadastro e aceite de convite; login
      continua funcionando) — IDT-05.
- [x] `test_aceite_de_email_registrado_continua_recusando` (guard L-048 intacto) —
      EDG-08.
- [ ] Gate completo verde nos dois dialetos (SQLite verde em 2026-11-25: 640
      passed, cobertura 99,09%; Postgres no CI — daemon docker indisponível no
      host).

---

### T3: PII/LGPD (I-5, I-10, I-11)

**What**:
- [ ] `privacy/politica.py`: `CATEGORIA_EMAIL`, `CATEGORIA_DOCUMENTO`, marcadores
      `[EMAIL]`/`[DOCUMENTO]` (PII-01).
- [ ] `privacy/redacao.py`: `_EMAIL`, `_CNPJ`, `_CPF` na ordem EMAIL → CNPJ → CPF
      → TELEFONE → ENDERECO → CEP → NOME (PII-01).
- [ ] `audit/retencao.py`: fail-safe `retention_days <= 0` (recusa + `logger.error`
      + `continue`) e `purgar_emails_de_convites` chamada de `purgar_expiradas`
      (PII-02/03).
- [ ] `db/models.py`: `Empresa.__table_args__` com
      `ck_empresa_retention_positiva`.
- [ ] Migração `f3c4d5e6f7a8` (down `f2b3c4d5e6f7`): constraint via
      `batch_alter_table` (PII-04).
- [ ] `repositories/empresas.py::create`: `ValueError` para `retention_days <= 0`
      (PII-04).

**Where**: `privacy/{politica,redacao}.py`, `audit/retencao.py`, `db/models.py`,
`repositories/empresas.py`, `alembic/versions/` (nova),
`tests/privacy/test_redacao.py`, `tests/audit/test_retencao.py`,
`tests/test_repositories.py`, `tests/test_migrations.py`
**Depends on**: T2 · **Reuses**: `redact`/`RedactedText`, `registrar_evento`
(categorias fluem), `purgar_expiradas` · **Requirement**: PII-01..04,
EDG-07 · **Tests**: unit + integration + migration · **Gate**: completo

**Done when**:
- [ ] `test_email_cpf_e_cnpj_sao_redigidos_antes_do_llm` (pergunta com os três →
      texto ao `FakeChatModel.mensagens_recebidas` só tem marcadores; histórico
      idem; auditoria registra `email`/`documento`) — falha hoje (I-5
      discriminante).
- [ ] `test_cpf_nao_e_capturado_como_telefone` (ordem das regexes; discriminante
      por categoria).
- [ ] `test_purga_zera_email_de_convites_expirados_e_usados` (linha preservada,
      `email=""`; convites válidos intocados) — I-10.
- [ ] `test_retention_days_zero_recusa_purga_e_loga_erro` (empresa com 0: nada
      purgado; outra empresa com prazo válido purga normalmente; `caplog` tem o
      erro) — PII-03/EDG-07.
- [ ] `test_insert_empresa_retention_days_zero_e_recusado` (`ValueError` no
      repositório e violação da constraint nos dois dialetos) — PII-04.
- [ ] Migração: constraint criada no upgrade e removida no downgrade (1 asserção
      por efeito).
- [ ] Gate completo verde nos dois dialetos.

---

### T5: Histórico — unicidade da conversa (I-9)

**What**:
- [ ] `db/models.py`: `Conversation.__table_args__` com
      `UniqueConstraint("empresa_id","user_id", name="uq_conversation_empresa_user")`.
- [ ] Migração `f4d5e6f7a8b9` (down `f3c4d5e6f7a8`): fail-fast de duplicatas
      listando pares/ids + `create_unique_constraint` via batch; downgrade remove.
- [ ] `repositories/conversations.py`: `get_or_create` com `begin_nested` +
      releitura em `IntegrityError` (HST-03); `get_by_user` ordena mais recente
      primeiro (HST-04).
- [ ] ADR da task: procedimento de resolução manual de conversas duplicadas
      (sugerido: manter a mais recente, arquivar/excluir as demais).

**Where**: `db/models.py`, `alembic/versions/` (nova),
`repositories/conversations.py`, `tests/test_repositories.py` (ou
`tests/copilot/test_conversations.py` conforme layout atual),
`tests/test_migrations.py`
**Depends on**: T3 · **Reuses**: padrão fail-fast, savepoint · **Requirement**:
HST-01..04, EDG-09 · **Tests**: integration + migration · **Gate**: completo

**Done when**:
- [ ] `test_migracao_aborta_com_conversas_duplicadas` (semear 2 conversas do mesmo
      par → `command.upgrade` levanta listando ids; limpo → upgrade cria e
      downgrade remove a constraint, round-trip nos dois dialetos) — falha hoje
      (I-9 discriminante).
- [ ] `test_get_or_create_concorrente_tem_uma_linha` (IntegrityError simulado por
      linha já existente → releitura devolve a existente; savepoint não envenena a
      transação) — HST-03.
- [ ] `test_leitura_devolve_a_conversa_mais_recente` (duplicata semeada → mais
      recente; após constraint, linha única) — HST-04.
- [ ] `test_dois_turnos_gravam_na_mesma_conversa` (fluxo do service: 2 turnos →
      1 conversa, 4 mensagens) — HST-01 integração.
- [ ] Gate completo verde nos dois dialetos.

---

### T4: Prompt injection/fontes (I-6)

**What**:
- [ ] `agents/base.py`: sanitização de marcadores (`(?im)^(\s*)fontes\s*:` →
      `fontes(dado):`) no conteúdo de ToolMessage intermediário (não-terminal)
      (FNT-01).
- [ ] `agents/base.py` + `state.py`: `tools_consultadas`
      (`Annotated[list[str], operator.add]`) acumulado por invocação de tool,
      intermediária e terminal (FNT-02).
- [ ] `copilot/service.py`: `_quebrar_resposta` reconhece estrutura apenas na
      ÚLTIMA linha; `validar_fontes(fontes, tools_consultadas)` aplicado antes de
      `registrar_turno` — vazio se nenhuma tool, divergência logada, nunca recusa
      o turno (FNT-01/02).
- [ ] Migração: nenhuma.

**Where**: `agents/base.py`, `state.py`, `copilot/service.py`,
`tests/agents/test_specialists.py`, `tests/copilot/test_service.py`
**Depends on**: T5 · **Reuses**: padrão `especialistas_visitados`, `_quebrar_resposta`
**Requirement**: FNT-01..02, EDG-03/04 · **Tests**: unit + integration ·
**Gate**: completo

**Done when**:
- [ ] `test_toolmessage_de_dado_importado_nao_carrega_marcador_de_estrutura` (tool
      fake devolvendo texto com `\nFontes: https://mal` → o conteúdo visto pelo
      modelo está neutralizado) — falha hoje (I-6 discriminante).
- [ ] `test_fontes_injetadas_no_meio_do_corpo_nao_sao_persistidas` (resposta com
      marcador injetado antes da linha real → fontes persistidas são as legítimas;
      texto injetado permanece literal no corpo).
- [ ] `test_turno_so_supervisor_persiste_fontes_vazias_com_log` (rota FINISH direta
      → `fontes=()` + warning de divergência; turno não é recusado) — FNT-02/EDG-03.
- [ ] `test_turno_com_tools_mantem_as_fontes_da_tool_comum` (tool terminal → fontes
      mantidas; `tools_consultadas` contém o nome da terminal).
- [ ] Gate completo verde nos dois dialetos.

---

### T6: Config/Rede LLM fail-closed (I-12, I-13)

**What**:
- [ ] `config.py`: `llm_timeout_s` (default 60, `gt=0`), `llm_max_retries`
      (default 1, `ge=0`, `le=5`) (CFG-01).
- [ ] `llm.py`: `ChatOpenAI(..., timeout=resolved.llm_timeout_s,
      max_retries=resolved.llm_max_retries)` (CFG-01).
- [ ] `config.py`: `auth_secret`/`llm_api_key` como `SecretStr`; validador usa
      `.get_secret_value()` (CFG-04).
- [ ] `auth/backend.py::get_jwt_strategy` e `auth/manager.py`: `.get_secret_value()`
      nos três pontos que consomem `auth_secret` (CFG-04).
- [ ] `config.py`: heurística `_execucao_prod` (`AMBIENTE=prod` OU host não-local
      do `database_url`); prod-like recusa segredo default/curto; `AMBIENTE=prod`
      recusa `database_url` não-Postgres (CFG-02/03).
- [ ] Migração: nenhuma.

**Where**: `config.py`, `llm.py`, `auth/backend.py`, `auth/manager.py`,
`tests/test_config.py` (ou arquivo existente de settings),
`tests/copilot/test_llm.py` (fábrica)
**Depends on**: T4 · **Reuses**: `model_validator` atual, `make_url`
**Requirement**: CFG-01..04, EDG-10 · **Tests**: unit · **Gate**: completo

**Done when**:
- [ ] `test_timeout_e_retries_chegam_ao_chat_openai` (fábrica captura kwargs; sem
      rede) — falha hoje (I-12 discriminante).
- [ ] `test_prod_recusa_segredo_default_e_curto` (mensagens atuais) e
      `test_host_externo_com_segredo_dev_nao_sobe_independente_do_ambiente`
      (`AMBIENTE=dev` + host externo → `ValueError`) — CFG-02/EDG-10, falha hoje
      (I-13 discriminante).
- [ ] `test_prod_recusa_database_url_sqlite` e
      `test_dev_local_com_segredo_default_sobe` (localhost/sqlite dev: OK) — CFG-03.
- [ ] `test_repr_nao_exponha_segredo_nem_api_key` — CFG-04.
- [ ] Testes de settings que mudam env usam `get_settings.cache_clear()` ou
      `Settings(_env_file=None)` (gotcha verificado).
- [ ] Gate completo verde nos dois dialetos.

---

### ACEITA: bateria de aceitação do épico

**What**:
- [ ] Teste de aceitação ponta-a-ponta do turno seguro (fake model + db_session):
      quota aplicada → PII redigida → turno gravado na conversa única → fontes
      válidas → tokens registrados (encadeia T1..T5).
- [ ] Atualizar o checklist de cobertura dos achados (C-1 + I-1..I-13) com o teste
      discriminante de cada um — nenhum achado sem teste que reprove a versão
      vulnerável.
- [ ] Conferir gate final: `make check` (format + lint + test) e matriz Postgres no
      CI.

**Where**: `tests/acceptance/` (padrão do `test_f1_mvp.py`),
`tests/test_migrations.py` (4 revisions novas)
**Depends on**: T1..T6 · **Requirement**: todos (SUCESSO do spec) · **Tests**:
acceptance · **Gate**: completo

**Done when**: todos os itens de "Success Criteria" do spec têm teste vermelho no
código pré-épico (verificado por amostragem de um subset via revert) e verde no
código pós-épico; CI (SQLite + Postgres) verde no PR de fechamento da integração.

---

## Checklist final do épico

- [ ] 6 PRs squash-mergeados contra `feat/seguranca-sweep` (cada um com tasks.md
      atualizado + testes no mesmo PR)
- [ ] 4 migrações encadeadas sem colisão (`alembic upgrade head` e `downgrade`
      provados nos dois dialetos)
- [ ] Self-review (ADR) + code review (`code-reviewer-agent`) em cada PR
- [ ] Gate do repo verde: `black --check`, `ruff check`, `pytest` ≥ 80% cobertura
- [ ] PR de release da integração documentado conforme fluxo de feature do
      AGENTS.md
