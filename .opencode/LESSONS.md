# Lições (memória de erros — projeto gestlog)

> Só erro real, já corrigido e observado; teto ~40 linhas; mais recente no topo.
> Formato: `Gatilho / Erro / Regra / Evidência`. Ver "Loop de auto-melhoria" no `AGENTS.md`.

## L-015 · 2026-09-22 · repositórios/domínio
- **Gatilho**: agrupar status em constantes de módulo num repositório que serve tanto à trilha quanto à purga.
- **Erro**: nomeei `_STATUS_TERMINAIS = ("aplicado", "falhou")`, mas o design define terminais como `rejeitado/aplicado/falhou`; o nome errado escondia que a trilha P2 ("correções aplicadas") é um recorte distinto da terminalidade.
- **Regra**: nomeie cada conjunto pelo critério real (`_STATUS_TERMINAIS` = transições finais do design; `_STATUS_TRILHA` = recorte de escrita) e explique no docstring por que a trilha difere do terminal.
- **Evidência**: self-review T2; `repositories/correcoes.py` passou a ter `_STATUS_TERMINAIS`/`_STATUS_TRILHA` e o teste `test_listar_trilha_ignora_rejeitado` fixa o recorte.

## L-014 · 2026-09-22 · git/PR
- **Gatilho**: branca/PR de task a partir de uma branch de integração criada ou atualizada nesta sessão.
- **Erro**: (a) criei `feat/f2-hitl` local sem push; `gh pr create --base` falhou ("Base ref must be a branch"); (b) cortei a branch da T2 da integração local desatualizada (sem upstream), faltando a T1.
- **Regra**: antes de cortar a task e de abrir o PR, sincronize a integração com o `origin` (setar upstream + `git push`/`git pull --ff-only`).
- **Evidência**: PR #47 e a branch da T2 tiveram de ser refeitos após `git push origin feat/f2-hitl` e `git pull --ff-only`.

## L-013 · 2026-09-22 · web/schema
- **Gatilho**: página HTML cujo `<select>`/validação usa um conjunto de valores que já existe como `Literal` no schema JSON.
- **Erro**: redeclarei `_PAPEIS = ("admin", "gestor", "operador")` no router, duplicando a fonte de verdade; ao mudar o domínio, formulário e API divergem em silêncio.
- **Regra**: derive opções e validação de uma única fonte (`get_args(Papel)`), nunca recopie o enum.
- **Evidência**: self-review T6; `admin_ui.py` passou a usar `get_args(Papel)` em vez da tupla local.

## L-012 · 2026-09-22 · html/js
- **Gatilho**: botão com ícone SVG + texto que precisa mudar de rótulo temporariamente (ex.: "Copiar conversa" → "Copiado!").
- **Erro**: usei `botao.textContent = "Copiado!"` e depois restaurei só o texto; `textContent` apaga TODOS os filhos, destruindo o `<svg>` na primeira cópia.
- **Regra**: ao trocar o rótulo de um controle com ícone, envolva o texto num `<span data-...>` e altere só o `textContent` desse span — nunca o do container.
- **Evidência**: code review do pente geral; `chat.html` ganhou `[data-rotulo-copiar]` e o JS preserva o SVG.

## L-011 · 2026-09-21 · web/testes
- **Gatilho**: remover da UI um controle/markup que outra camada consome (ex.: botões de feedback do chat).
- **Erro**: rodei só `tests/web/` e esqueci que `tests/acceptance/test_f1_mvp.py` raspava o HTML do chat para obter o id da recomendação — quebrou após a remoção.
- **Regra**: ao remover/renomear markup, rode a suíte **completa** e prefira buscar ids no banco/repositório em vez de extraí-los do HTML renderizado.
- **Evidência**: `test_cop_aceite_registra_decisao` — agora usa `_recomendacao_do_usuario(fabrica_sync, email)`.

## L-009 · 2026-09-21 · web/form
- **Gatilho**: rota web com `Form()` obrigatório que deve **reexibir o formulário** quando o input é inválido.
- **Erro**: `Annotated[str, Form()]` com valor vazio vira `None` no FastAPI → responde **422 JSON** ("missing"), sem cair no handler que re-renderiza o HTML.
- **Regra**: dê default `""` aos campos `Form()` e deixe o schema Pydantic rejeitar; todo input inválido passa pelo mesmo caminho de erro renderizado.
- **Evidência**: `tests/web/test_cadastro.py::test_cadastro_nome_empresa_vazio_recusa` (422 antes, 400 após).
