# Lições (memória de erros — projeto gestlog)

> Só erro real, já corrigido e observado; mais recente no topo.
> Formato: `Gatilho / Erro / Regra / Evidência`. Ver "Loop de auto-melhoria" no `AGENTS.md`.

## L-027 · 2026-09-25 · repositório/SQLAlchemy
- **Gatilho/Erro**: para silenciar o `C416` do ruff, reescrevi um mapeamento de linhas SQLAlchemy como `dict(self.session.execute(stmt).tuples())`; passou no lint, mas quebrou em runtime (`TypeError: 'ChunkedIteratorResult' object is not subscriptable`) nos 4 testes de histórico.
- **Regra**: sugestão de linter sobre iterável de `Row` não é autofix seguro — mantenha o mapeamento explícito (`{linha.id: linha.email for linha in ...}`) e só aplique o rewrite após rodar o teste.
- **Evidência**: self-review T11 (`repositories/users.py::emails`; gate falhou e voltou a verde ao reverter).

## L-026 · 2026-09-25 · web/contexto de template
- **Gatilho/Erro**: ao passar um flag de permissão ao template, hardcodei `pode_aprovar: True` numa rota admin em vez de derivar do conjunto canônico (`PAPEIS_APROVADORES`); o menu parecia certo, mas ignorava a fonte única.
- **Regra**: todo flag de contexto derivado de um conjunto de papéis/estados deve ser calculado da constante canônica, mesmo quando o valor atual é sempre o mesmo.
- **Evidência**: self-review T10 (`web/admin_ui.py`, corrigido para `admin.papel in PAPEIS_APROVADORES`).

## L-024 · 2026-09-23 · testes/conjunto (absorve L-021, L-023)
- **Gatilho/Erro**: guard, mapa ou laço cobre um **conjunto** (tipos, estados, empresas), mas o teste exercita só um representante — os demais passariam numa regressão.
- **Regra**: um teste por elemento do conjunto (tipo / estado terminal / empresa), asseverando a não-alteração; cobertura de um ramo não valida os demais.
- **Evidência**: T7 (aplicar nos 3 tipos), T8 (3 estados terminais), T9 (2 empresas com prazos distintos).

## L-025 · 2026-09-23 · doc/contrato de auditoria (absorve L-019, L-020)
- **Gatilho/Erro**: transcrever/resumir um contrato de design omitindo qualificadores (faltou "`valor` truncado", `motivo` = código, a coluna do corte `created_at` vs. `decidido_em`) — e confiar em constraint de coluna não imposta (SQLite `String(255)`).
- **Regra**: transcreva o contrato **integralmente**, desambigue homônimos, **nomeie a coluna** do corte temporal e trunque explicitamente no call site.
- **Evidência**: self-review T6/T7/T9 (`audit/eventos.py`, `_valor_auditavel`, `correcoes.py::purgar_expiradas`).

## L-022 · 2026-09-23 · processo/ADRs
- **Gatilho/Erro**: deleguei a ADR ao subagente sem validar a saída; T1–T6 saíram com 4 seções (faltava "Roadmap Imediato" e, na T3, "Validação").
- **Regra**: carregue a skill `write-fluid-hybrid-adr` e **gere/valide a ADR você mesmo** (checklist das 5 seções) antes de fechar a task.
- **Evidência**: correção do usuário; PR #55 (`docs/f2-adr-fluido`) alinhou T1–T6.

## L-018 · 2026-09-23 · testes/coleta e suíte completa (absorve L-011)
- **Gatilho/Erro**: criei `tests/correcoes/test_servico.py` com basename já usado em `tests/ingestion/` (sem `__init__.py`) → "import file mismatch"; e remover markup pode quebrar testes que raspa HTML.
- **Regra**: basename **único** por arquivo de teste; ao remover/renomear markup, rode a suíte **completa** e busque ids no repositório, não no HTML.
- **Evidência**: T5 (`test_servico_fila.py`); L-011 em `tests/acceptance/test_f1_mvp.py`.

## L-016 · 2026-09-23 · domínio/tipagem (absorve L-017)
- **Gatilho/Erro**: ao extrair helper, avaliei `getattr(...)` antes de validar o campo (`AttributeError` em vez de erro de domínio); e anotei `-> list` apagando a união real.
- **Regra**: preserve a ordem de avaliação (valide **antes** do `getattr`) e anote a união real (`list[str] | list[float]`), não `list` cru.
- **Evidência**: T4; `completude.valor_atual` e `sugestoes._valores`.

## L-013 · 2026-09-23 · fonte única (absorve L-015)
- **Gatilho/Erro**: redeclarei um conjunto já existente (papéis/status) e nomeei constantes pelo critério errado (`_STATUS_TERMINAIS` sem `rejeitado`).
- **Regra**: derive de uma única fonte (`get_args(Papel)`, `_CAMPOS`) e nomeie cada conjunto pelo **critério real** (`_STATUS_TERMINAIS` × `_STATUS_TRILHA`).
- **Evidência**: T6 UI (`admin_ui.py`); `repositories/correcoes.py` (T2).

## L-014 · 2026-09-22 · git/PR
- **Gatilho/Erro**: branch/PR de task a partir de integração criada nesta sessão sem upstream → `gh pr create --base` falhou e a task saiu sem a anterior.
- **Regra**: antes de cortar a task e abrir o PR, sincronize a integração com o `origin` (`git push`/`git pull --ff-only`).
- **Evidência**: PR #47 e branch da T2 refeitos.

## L-009 · 2026-09-21 · web/form e html/js (absorve L-012)
- **Gatilho/Erro**: `Annotated[str, Form()]` vazio vira `None` no FastAPI → 422 JSON em vez do HTML re-renderizado; trocar rótulo de botão com ícone via `textContent` do container apaga o `<svg>`.
- **Regra**: default `""` em `Form()` (o Pydantic rejeita e o HTML re-renderiza); envolva o texto do ícone num `<span data-...>` e altere só o `textContent` dele.
- **Evidência**: `tests/web/test_cadastro.py::...`; code review (`chat.html`).
