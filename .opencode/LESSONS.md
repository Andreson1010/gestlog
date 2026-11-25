# Lições (memória de erros — projeto gestlog)

> Só erro real, já corrigido e observado; mais recente no topo. Formato detalhado em AGENTS.md ("Loop de auto-melhoria").

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
