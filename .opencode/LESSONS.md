# Lições (memória de erros — projeto gestlog)

> Só erro real, já corrigido e observado; mais recente no topo.
> Formato: `Gatilho / Erro / Regra / Evidência`. Ver "Loop de auto-melhoria" no `AGENTS.md`.

## L-033 · 2026-09-28 · web/formatação tela×CSV
- **Gatilho/Erro**: no relatório de transporte a tela renderizava o datetime cru (`{{ registro.previsao_entrega }}` → `2026-06-10 00:00:00+00:00`) enquanto o CSV usava `.isoformat()` (`2026-06-10T00:00:00`); o requisito exige que as linhas do CSV correspondam exatamente à tabela exibida (REL-28/AC9).
- **Regra**: quando tela e exportação compartilham a mesma tabela, formate o valor na tela com o **mesmo** formatador do CSV (aqui `isoformat()`), nunca deixe a conversão implícita de `str(datetime)` divergir; cubra com teste que compara o texto da página e a célula do CSV.
- **Evidência**: self-review relatórios (`web/templates/relatorios.html`, `web/relatorios.py::_data`); `tests/web/test_relatorios.py::test_pagina_e_csv_transporte_exibem_mesma_data`.

## L-032 · 2026-09-28 · tipagem/dispatcher
- **Gatilho/Erro**: helpers que despacham por domínio (`_resumo`, `_cabecalho_linhas` em `web/relatorios.py`) e métodos que operam sobre `Select` do histórico ficaram sem anotação de retorno/parâmetro (`def _resumo(...):`, `base: Select`, `-> list`), apagando a união real de retorno e o tipo do alvo.
- **Regra**: anote explicitamente o retorno de dispatchers (união dos dataclasses, ex. `_Resumo = ResumoEstoque | ResumoTransporte | ResumoFornecedores`) e os parâmetros genéricos (`Select[tuple[CatalogoHistorico]]`, `list[ColumnElement[bool]]`); não deixe o tipo inferido por omissão.
- **Evidência**: self-review relatórios; `black`/`ruff`/`pytest` verdes após os ajustes.

## L-031 · 2026-09-28 · testes/timezone SQLite
- **Gatilho/Erro**: comparei em teste `snapshot.importado_em == job.created_at` e `registro.previsao_entrega == previsao` (ambos `tzinfo=UTC`); o SQLite devolve o datetime lido **naive** (sem tz), então o gate ficou vermelho mesmo com o código de produção correto.
- **Regra**: ao asseverar valor relido do SQLite contra datetime aware, normalize antes (`.replace(tzinfo=UTC)`); não "conserte" o código de produção nem passe `expire_on_commit`/`timezone` só para o teste.
- **Evidência**: T1–T3 da feature relatórios (`tests/ingestion/test_servico.py`, `tests/test_repositories.py`); gate `--no-cov` vermelho→verde.

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
