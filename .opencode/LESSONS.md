# Lições (memória de erros — projeto gestlog)

> Só erro real, já corrigido e observado; mais recente no topo. Formato detalhado em AGENTS.md ("Loop de auto-melhoria").

## L-057 · 2026-11-25 · WSL sem distro explícita cai no docker-desktop
Gatilho/Erro: no self-review da T3, chamei `wsl bash -lc "..."` três vezes — o distro DEFAULT do host é `docker-desktop` (sem bash) e o Windows `uv run` esbarrou no `.venv` Linux do repo ("Acesso negado" em `lib64`); só `wsl -d Ubuntu bash -lc` funciona. Regra: neste host, TODO comando de gate/WSL leva `-d Ubuntu` explicitamente (`wsl -d Ubuntu bash -lc "cd /mnt/c/... && uv run ..."`); o `.venv` do repo é Linux — nunca invocar `uv`/`pytest` pelo shell do host. Evidência: "bash: not found" 3x; gate verde na T3 (660 passed) via `-d Ubuntu`.

## L-056 · 2026-11-25 · índice único novo sem auditar IntegrityError nas rotas
Gatilho/Erro: a T2 criou o índice funcional `uq_user_email_ci` (case-insensitive) e alargou a superfície de corrida de cadastro, mas a rota API `/onboarding` não capturava `IntegrityError` — corrida de cadastro case-divergente devolvia 500 (a rota web `/cadastro` já tratava com 409). Regra: ao introduzir/restringir um índice único que amplie a unicidade, auditar TODAS as rotas/casos de uso que gravam no recurso — handler de `IntegrityError` com rollback e resposta de conflito em cada uma. Evidência: self-review da T2 — `test_onboarding_corrida_de_email_retorna_409` + handler em `onboarding.py` (commit `3550264`).

## L-055 · 2026-11-25 · diff "em massa" cross-EOL antes de reverter
Gatilho/Erro: após rodar `black -w` pelo WSL, li `git diff --stat` TAMBÉM no WSL e vi 260 arquivos/43k linhas "reformatadas" — concluí dano em massa e quase executei `git checkout -- .` (que descartaria edições legítimas pendentes). Regra: git do host (`core.autocrlf=true`) e git do WSL (sem config) divergem sobre EOL no mesmo repo — estado de working copy verifica-se pelo git do HOST antes de qualquer reversão em massa; diff/stat do WSL em repo Windows é ruído CRLF. Evidência: `git status`/`diff --stat` do host mostraram só 5 arquivos reais (2 do black, 2 meus edits E501, LESSONS).

## L-054 · 2026-11-25 · tool call fake fora do formato canônico
Gatilho/Erro: no teste de estimativa de tokens construí tool call fake como `{"name","args"}` sem `id`/`type` — o AIMessage do langchain recusou (`tool_call() missing 'id'`) e o teste falhou por shape, não pelo critério. Regra: TODA tool call fake segue o formato completo do AGENTS.md (`{"name","args","id","type":"tool_call"}`) — inclusive quando serve só de payload de contagem; conferir o contrato do fixture antes de inventar dict mínimo. Evidência: `tests/agents/test_base.py::test_estimativa_cobre_tool_calls_do_payload` — TypeError no verde, corrigido com o formato canônico.

## L-053 · 2026-11-25 · stash não pega mudança já commitada
Gatilho/Erro: para rodar o teste discriminante contra a versão vulnerável, tentei `git stash push -- src/gestlog/agents/supervisor.py` — "No local changes to save": a mudança da task estava COMMITADA na branch, e stash só move alterações do working tree. Regra: para testar contra versão de outra ref de um arquivo commitado, `git restore --source <ref> -- <path>` (revertendo com `git restore --source HEAD -- <path>` e conferindo `git status`); stash é para working tree suja. Evidência: self-review da T1 — revert empírico do discriminante C-1 (`test_turno_so_supervisor_conta_tokens` → `assert 0 > 0` na versão de `main`).

## L-052 · 2026-11-25 · alvo do alembic downgrade é o pai da mudança
Gatilho/Erro: no teste da migração T1 usei `command.downgrade(cfg, _REV_QUOTA)` para "remover a coluna" — o downgrade vai ATÉ a revision, e f1a2b3c4d5e6 é justamente a que CRIA a coluna; o assert final pegou a coluna ainda presente. Regra: para provar que uma revision X foi desfeita, `downgrade` alveja o PAI de X (padrão do próprio repo: `downgrade(cfg, "d5e6f8a2b7c4")` no teste de convites); reconfirmar a semântica "upgrade/downgrade TO rev" antes de escrever o round-trip. Evidência: `tests/test_migrations.py::test_migracao_quota_da_empresa_coluna` — assert falhou, corrigido para `downgrade(cfg, "e8a1c5d9f3b7")`.

## L-051 · 2026-11-25 · contagem declarada divergente da lista real
Gatilho/Erro: declarei "21 para remover, 14 para manter" com a tabela listando só 19 — o usuário aprovou "remover as 21" e a execução literal deixaria 2 de fora. Regra: antes de pedir aprovação sobre um conjunto, reconcile a contagem com a listagem item a item; diferença revela item implícito não decidido. Evidência: podar `.agents/skills/` nesta sessão — reconciliado em execução (+`improve-codebase-architecture`, +`research`).

## L-050 · 2026-11-06 · shell/pwsh destrói UTF-8 de .md edits
Gatilho/Erro: usei `Get-Content -Raw`/`Set-Content` (pwsh) para trocar texto em ADRs .md — a leitura/wait-write em encoding gerado corrompeu acentos ("número"→"nmero") em DOIS arquivos; e patches salvos via `Out-File` vieram com CRLF e falhavam `git apply` contra blob LF. Regra: editar arquivo via ferramenta de edição do agente (Read/Edit/Write), nunca cmdlets de conteúdo pwsh; patch p/ `git apply` gerar com `[IO.File]::WriteAllText` e LF (verify `--check` antes de aplicar). Evidência: revert+redo de `docs/adr/{ad-015,empresa-ativa}-...md`; patch `models_wip_convite.patch` reprovado 2x.

## L-049 · 2026-11-06 · premissa de estado do repo sem conferir filesystem
Gatilho/Erro: no PR #78, self-review/removeu a regra `graphify-out/` do `.gitignore` sob "não há graphify-out aqui" — o diretório EXISTIA (grafo gerado do próprio gestlog, ignorado por design no #41); a busca usada respeita `.gitignore` e era cega ao próprio artefato avaliado, desprotegendo 2GB+ de dado ignorado ao `git add .`. Regra: premissa "caminho não existe / regra morta" verifica com `git status --ignored` ou listagem no filesystem — ferramenta de busca que respeita `.gitignore` nunca confirma um artefato ignorado. Evidência: review I-1 do PR #78 (refutação por `GRAPH_REPORT.md`, commit `5845358`); regra restaurada em `8a3e65d`.

## L-048 · 2026-11-06 · convite/token como prova de posse de e-mail
Gatilho/Erro: desenhei o aceite do convite redefinindo a senha de `User` global já registrado ("convite-assume-acesso") com o token entregue AO CONVIDADOR — qualquer pessoa pode criar empresa via `/onboarding`, convidar o e-mail da vítima e tomar a conta (takeover cross-tenant); CRITICAL achado no review independente do PR #80. Regra: token que o EMISSOR possui nunca prova posse do e-mail; fluxo sem autenticação NUNCA altera credencial de usuário existente — convite só cria conta nova, com guard "e-mail registrado → recusa" (defense-in-depth) e teste cross-tenant que discrimina a versão vulnerável (guard de vínculo na empresa convidante não basta). Evidência: review CRITICAL PR #80; fix em `accounts.py` (`criar_convite`/`aceitar_convite`) + `ConviteEmailRegistradoError` → commit `d77c5b6`; testes `test_convite_de_outra_empresa_nao_toca_credencial_da_vitima`/`test_convite_para_email_registrado_retorna_409`.

## L-047 · 2026-11-06 · rate-limit/ordem da poda dentro da contagem
Gatilho/Erro: implementei a poda do `RateLimiter` DEPOIS do `setdefault` com gatilho `>` — a chave corrente era removida no meio da própria contagem e o `append` gravava num deque órfão fora do dict (tentativa sem registro, limite furável); `>` sobre tamanho pré-inserção também não disparava na borda, revelado pelo teste. Regra: poda de estrutura mutável por uso só ANTES de inserir a chave corrente; gatilho por tamanho que testa pré-inserção usa `>=`; teste da borda (teto monkeypatchado) na frente — deixou fechar o ciclo vermelho→verde. Evidência: `src/gestlog/web/rate_limit.py` (`_podar` antes do `setdefault`, `>=`); `tests/web/test_rate_limit.py::test_limitador_poda_chaves_sem_marca_viva`; conserto no self-review D5 (→ `11bf860`).

## L-046 · 2026-11-06 · htmx/escopo do sse-swap da extensão SSE
Gatilho/Erro: acrescentei `sse-swap="fontes"` num div IRMÃO do elemento com `sse-connect` — a extensão 2.2.2 acha a fonte só em ANCESTRAIS (`getClosestMatch`) e os eventos só chegam a ela se houver `hx-ext="sse"` na ascendência (`Ft/Un` do htmx 2.0.4): elemento órfão, evento `(event: fontes)`.postMessage nunca renderizado, e teste SSE só validava o lado do servidor. Regra: em `htmx-ext-sse`, `hx-ext="sse"` + `sse-connect` + `sse-close` vão no ancestral comum a TODOS os `sse-swap`; antes de aninhar atributos de extensão, leia o código da extensão quanto a como acha fonte e listeners (não confie no uso que "parece" idiomático). Evidência: review D2+D3+D4 de 2026-11-06; sse.js (bigskysoftware/htmx-extensions) `registerSSE`/`ensureEventSourceOnElement`; conserto em `chat_turno.html`.

## L-045 · 2026-11-06 · docs/checkbox parcial num item multi-dívida
Gatilho/Erro: no STATE.md marquei `[x]` no item "Débitos técnicos herdados" com 3 dos 5 débitos ainda pendentes (recaída direta da L-044, agora por subitem). Regra: item com parte quitada parte pendente fica `[ ]` listando só o residual, com nota da data dos subitens quitados; se necessário, fatie o item. Evidência: STATE.md linhas 611–616 corrigidas no review D2+D3+D4 de 2026-11-06.

## Anteriores (uma linha por erro)

- **L-044** (2026-10-28): checkbox de dívida `[x]` antes de implementar (STATE.md AD-015) → só com código escrito E gate verde; implemente primeiro, documente depois.
- **L-043** (2026-10-26): allowlist do revisor contornável (refspec, `branch -f`, negação ancorada, `--no-index`) → negação por flag casa em QUALQUER posição e vem DEPOIS dos allows; valide EXECUTANDO bypass com ruleset novo.
- **L-042** (2026-10-26): comitei CONTEXT.md com estado inexistente no HEAD; invalidei achado sem conferir commit → confirme com `git status`/`git show` antes de alegar estado (absorve L-041).
- **L-040** (2026-10-22): `bash "*": ask` travou subagente não-interativo 3x → allowlist read-only + catch-all `deny` (nunca `ask`); prompt sem pipe/variável/script.
- **L-039** (2026-10-22): pedido ambíguo lido como decisão (builders p/ GLM free) → quando a verificação quebra a premissa do pedido, pare e pergunte antes de editar config.
- **L-038** (2026-10-22): matriz Postgres ligada só ao `db_session`; `test_db.py` ficou em SQLite → ao criar matriz de dialetos, migre todo fixture de banco e meça a cobertura alegada.
- **L-037** (2026-10-07): teste de migração validava 1 de 5 colunas, sem downgrade → 1 asserção por coluna (valor + efeito no JOIN) em `upgrade` **e** `downgrade`.
- **L-035** (2026-10-06): recriei venv em 3.13 para driblar o SAC; bloqueio só migrou de DLL → não troque interpretador por causa do SAC; gate no WSL2 ou CI.
- **L-034** (2026-10-06): `head`/`tail`/`rg` não existem no pwsh; backtick e `"$VAR"` em `wsl bash -lc` quebram → cmdlets nativos; `--body-file`; comandos WSL em script `.sh`.
- **L-032** (2026-09-28): dispatcher/`Select` sem anotação apagavam a união → anote `_Resumo = A | B | C` e `Select[tuple[X]]`; valide antes do `getattr`.
- **L-031** (2026-09-28): datetime aware relido do SQLite volta naive → normalize (`.replace(tzinfo=UTC)`) no teste, sem alterar produção.
- **L-029** (2026-09-27): asserção em affordance/ORM truthy e autofix de linter sobre `Row` não são seguros → ancore no dado/estado do critério; 1 teste por elemento do conjunto (absorve L-026/L-028).
