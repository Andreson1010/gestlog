# Lições (memória de erros — projeto gestlog)

> Só erro real, já corrigido e observado; mais recente no topo.
> Formato: `Gatilho / Erro / Regra / Evidência`. Ver "Loop de auto-melhoria" no `AGENTS.md`.

## L-043 · 2026-10-26 · permissões/allowlist de git
- **Gatilho/Erro**: liberei `git fetch origin*`, `git branch*` e `git diff/log/show*` no revisor sem validar bypass: refspec reescrevia `origin/main`, `git branch -f/-D/-m` reescrevia refs locais e o fuzzing da r3 mostrou que negação ancorada por posição é contornável (git aceita flag em qualquer lugar — `git diff --stat --output=arquivo` casou o allow e gravou). **Regra**: negação por flag deve casar a flag em QUALQUER posição (`git diff *--output*`) e vir DEPOIS dos allows (última regra vence); valide a allowlist EXECUTANDO os comandos de bypass, não por leitura. Evidência: review do #77 (rodadas 1–3), fuzzing real; consertos em `475123a`, `10575e1` + fix.

## L-042 · 2026-10-26 · handoff/estado commitado
- **Gatilho/Erro**: comitei no PR #76 um CONTEXT.md descrevendo estado inexistente no HEAD (config listada como "não commitada" já dentro do commit; ADR recém-commitada listada como pendente) — review achou M-1. **Regra**: antes de commitar o handoff, reclasse as seções para o estado resultante do próprio commit (não o anterior); confirme com `git status`/`git show`. Evidência: review do #76, M-1 corrigido em `7d58e04`.

## L-041 · 2026-10-22 · review/validação de achado
- **Gatilho/Erro**: o review do #74 apontou `.opencode/CONTEXT.md`/`LESSONS.md` como commitados e eu declarei o achado "inválido" por supor que eram mudanças locais; `git show --name-only 24128ac` provou que estavam no commit. **Regra**: antes de invalidar achado por escopo, confirme no git o que o commit contém — suposição não vale. Evidência: registro corrigido no CONTEXT.

## L-040 · 2026-10-22 · subagentes/permissões
- **Gatilho/Erro**: `code-reviewer-agent` travou 3x no #74 porque `bash "*": ask` bloqueia em subagente não-interativo (o modelo tenta contornar e encerra sem relatório). **Regra**: subagente precisa de allowlist read-only + catch-all `deny` (falha rápida, nunca `ask`) e prompt proibindo pipe/variável/script. Evidência: `opencode debug agent` → `bash *: deny`; review do #74 concluído.

## L-039 · 2026-10-22 · agentes/modelos
- **Gatilho/Erro**: "caso sim, coloque builders em GLM free" foi lido como gatilho e eu troquei o fluxo sem confirmar, mesmo com o free inferior ao pago; usuário corrigiu. **Regra**: quando a verificação quebra a premissa do pedido, pare e pergunte antes de editar config. Evidência: revertido para pago (builders `opencode-go/glm-5.3-flash`, revisor `opencode-go/deepseek-v4.1-flash`).

## L-038 · 2026-10-22 · testes/cobertura da matriz
- **Gatilho/Erro**: matriz Postgres ligada só ao `db_session`; `tests/test_db.py` ficou em SQLite e o STATE dizia "~92 testes" (medido 117/120). **Regra**: ao criar matriz de dialetos, migre todo fixture de banco e meça a cobertura alegada. Evidência: `tests/test_db.py` → `db_session`; AD-031 corrigida.

## L-037 · 2026-10-07 · testes/migração de dados
- **Gatilho/Erro**: teste da migração `b7d2e9a4f108` validava 1 de 5 colunas e não cobria `downgrade` com dado (reincidiu L-029). **Regra**: 1 asserção por coluna (valor + efeito no JOIN) em `upgrade` **e** `downgrade`. Evidência: `tests/test_migrations.py::test_migracao_normaliza_fk_user_para_guid`.

## L-036 · 2026-10-06 · alembic/geração
- **Gatilho/Erro**: brigar com `script.py.mako` para deixá-lo black-clean; `${repr()}`/`${imports}` quebram e o autogenerate não passa pelo template. **Regra**: deixe o `[post_write_hooks]` do `alembic.ini` (ruff --fix + black) formatar o arquivo gerado. Evidência: PR #72 (`f348d0b`).

## L-035 · 2026-10-06 · ambiente/Windows SAC
- **Gatilho/Erro**: recriei o venv em 3.13 para driblar o Smart App Control; o bloqueio só migrou de DLL (`psycopg`). **Regra**: não troque interpretador por causa do SAC; rode o gate no WSL2 sobre `/mnt/c` (venv fora do repo) ou no CI. Evidência: `gestlog-gate` → 573 passed.

## L-034 · 2026-10-06 · shell/pwsh + git/PR
- **Gatilho/Erro**: `head`/`tail`/`rg` não existem no pwsh; backtick em `--body` e `"$VAR"`/`$(...)` no `wsl bash -lc` quebram. **Regra**: cmdlets nativos (`Select-Object`/`Select-String`); markdown via `--body-file`; comandos WSL em script `.sh`; sincronize `origin` antes do PR. Evidência: PRs #47/#55/#67/#68.

## L-032 · 2026-09-28 · tipagem (dispatchers/Select)
- **Gatilho/Erro**: dispatcher e `Select` sem anotação apagavam a união real. **Regra**: anote `_Resumo = A | B | C` e `Select[tuple[X]]`; valide antes do `getattr`. Evidência: `audit/eventos.py`; T6/T7/T9.

## L-031 · 2026-09-28 · testes/timezone SQLite
- **Gatilho/Erro**: datetime aware relido do SQLite volta naive. **Regra**: normalize (`.replace(tzinfo=UTC)`) no teste, sem alterar produção. Evidência: `tests/test_repositories.py`.

## L-029 · 2026-09-27 · testes/ancoragem (absorve L-026/L-028)
- **Gatilho/Erro**: asserção em affordance/ORM truthy e autofix de linter sobre `Row` não são seguros. **Regra**: ancore no dado/estado do critério; 1 teste por elemento do conjunto. Evidência: `test_inc_02`; `repositories/users.py::emails` (revertido).
