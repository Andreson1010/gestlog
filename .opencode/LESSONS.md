# Lições (memória de erros — projeto gestlog)

> Só erro real, já corrigido e observado; mais recente no topo.
> Formato: `Gatilho / Erro / Regra / Evidência`. Ver "Loop de auto-melhoria" no `AGENTS.md`.

## L-030 · 2026-09-27 · testes/tamanho de arquivo
- **Gatilho/Erro**: entreguei `tests/acceptance/test_f2_hitl.py` com 1040 linhas e, de uma vez só, sentinela acidental (`dataclass_placeholder`) e helper indefinido (`_fabrica`); o usuário apontou o estouro do teto de 800 do `AGENTS.md`.
- **Regra**: dimensione antes de escrever — se o estimado passar de 800 linhas, modularize desde o início (fixtures em `conftest.py`, helpers em módulo de apoio sem prefixo `test_`, arquivos por grupo de critério) e rode o gate por arquivo; não grave um arquivo inteiro sem revisar.
- **Evidência**: correção do usuário; refatorado em `tests/acceptance/{conftest,f2_suporte,test_f2_hitl,test_f2_hitl_decisao,test_f2_hitl_trilha,test_f2_hitl_chat}.py` (≤487 linhas cada).

## L-029 · 2026-09-27 · testes/ancoragem da asserção (absorve L-028)
- **Gatilho/Erro**: asseverei por affordance/objeto — `aria-label="Aprovar…"` para "indicar campo faltante" (INC-02), `assert item_correcao(...)` (ORM sempre truthy) e `"—" in pagina.text` (símbolo solto).
- **Regra**: ancore a asserção ao dado/estado que o critério exige (`<td>campo</td>`, `.status == "aplicado"`, `.motivo_falha == …`), nunca a botão condicional, objeto truthy ou caractere solto.
- **Evidência**: T12 aceitação — `test_inc_02` (gate vermelho→verde), `test_apr_05`/`test_sug_05` (self-review), `test_edg_02` (code review).

## L-028 · 2026-09-25 · lint/SQLAlchemy (era L-027)
- **Gatilho/Erro**: para silenciar o `C416`, reescrevi mapeamento de linhas SQLAlchemy como `dict(execute(...).tuples())`; lint verde, runtime quebrado (`ChunkedIteratorResult` não subscriptável).
- **Regra**: sugestão de linter sobre iterável de `Row` não é autofix seguro — mantenha o mapeamento explícito e só aplique o rewrite após rodar o teste.
- **Evidência**: self-review T11 (`repositories/users.py::emails`; revertido).

## L-027 · 2026-09-25 · fonte única (absorve L-026, L-013)
- **Gatilho/Erro**: hardcodei flag de papel (`pode_aprovar: True`) e redeclarei/nomeei conjunto existente pelo critério errado (`_STATUS_TERMINAIS` sem `rejeitado`).
- **Regra**: todo flag/conjunto deriva de uma única fonte canônica (`PAPEIS_APROVADORES`, `get_args(Papel)`, `_CAMPOS`) e é nomeado pelo critério real.
- **Evidência**: self-review T10 (`web/admin_ui.py`); `repositories/correcoes.py` (T2).

## L-026 · 2026-09-23 · testes/conjunto (era L-024)
- **Gatilho/Erro**: guard/mapa cobre um conjunto (tipos, estados, empresas), mas o teste exercita só um representante — os demais passariam numa regressão.
- **Regra**: um teste por elemento do conjunto, asseverando a não-alteração; cobrir um ramo não valida os demais.
- **Evidência**: T7 (3 tipos), T8 (3 estados terminais), T9 (2 empresas com prazos distintos).

## L-025 · 2026-09-23 · doc/contrato + tipagem (absorve L-025, L-016)
- **Gatilho/Erro**: resumi contrato omitindo qualificadores (`valor` truncado, `motivo`=código, coluna do corte) e confiei em constraint do SQLite; anotei `-> list` apagando a união real e avaliei `getattr` antes de validar.
- **Regra**: transcreva o contrato integralmente e nomeie o corte; anote a união real e valide **antes** do `getattr`; não confie em constraint não imposta.
- **Evidência**: T6/T7/T9 (`audit/eventos.py`, `_valor_auditavel`, `purgar_expiradas`); T4 (`completude.valor_atual`).

## L-024 · 2026-09-23 · processo/ADRs (era L-022)
- **Gatilho/Erro**: deleguei a ADR sem validar; T1–T6 saíram com 4 seções (faltava "Roadmap Imediato"; T3 sem "Validação").
- **Regra**: carregue `write-fluid-hybrid-adr` e gere/valide a ADR você mesmo (checklist das 5 seções) antes de fechar a task.
- **Evidência**: correção do usuário; PR #55 alinhou T1–T6.

## L-023 · 2026-09-22 · testes/coleta + git/PR (absorve L-018, L-014)
- **Gatilho/Erro**: basename de teste repetido → "import file mismatch"; remover markup quebrou testes que raspam HTML; integração sem upstream → `gh pr create --base` falhou.
- **Regra**: basename único por arquivo de teste; rode a suíte completa ao mexer em markup; sincronize a integração com o `origin` antes de abrir o PR.
- **Evidência**: T5 (`test_servico_fila.py`); PR #47 e branch da T2 refeitos.

## L-022 · 2026-09-21 · web/form (era L-009)
- **Gatilho/Erro**: `Annotated[str, Form()]` vazio vira `None` → 422 JSON; trocar rótulo de botão com ícone via `textContent` do container apaga o `<svg>`.
- **Regra**: default `""` em `Form()` (Pydantic rejeita e o HTML re-renderiza); envolva o texto do ícone num `<span data-...>` e altere só ele.
- **Evidência**: `tests/web/test_cadastro.py`; code review (`chat.html`).
