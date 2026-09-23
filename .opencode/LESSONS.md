# Lições (memória de erros — projeto gestlog)

> Só erro real, já corrigido e observado; teto ~40 linhas; mais recente no topo.
> Formato: `Gatilho / Erro / Regra / Evidência`. Ver "Loop de auto-melhoria" no `AGENTS.md`.

## L-025 · 2026-09-23 · documentação/contrato
- **Gatilho**: documentar o corte temporal de um método numa entidade que tem **dois** timestamps candidatos (`created_at` e `decidido_em`).
- **Erro**: o docstring de `CorrectionRepository.purgar_expiradas` dizia só "anteriores a ``limite``", sem nomear a coluna; como `listar_trilha` corta por `decidido_em`, o leitor poderia supor o campo errado (qualificador do design omitido — reforça L-019).
- **Regra**: ao documentar corte temporal, nomeie a coluna explicitamente (`created_at`, não `decidido_em`) sempre que houver mais de um timestamp possível.
- **Evidência**: self-review T9; docstring passou a citar ``created_at`` e a contrastar com ``decidido_em``.

## L-024 · 2026-09-23 · testes/multitenant
- **Gatilho**: incluir uma nova tabela multitenant (`item_correcao`) num laço de retenção que percorre empresas e purga por prazo.
- **Erro**: os testes só cobriam a nova tabela numa única empresa; a composição por empresa (prazo próprio + `empresa.id`) não tinha teste de integração, então um `limite`/escopo errado passaria em silêncio.
- **Regra**: ao estender um laço multitenant para uma nova tabela, replique os testes de isolamento/prazo-por-empresa que já existem para as tabelas antigas (espelha L-021/L-023).
- **Evidência**: self-review T9; `test_purga_itens_isola_entre_empresas` (vencida 30d removida, retida 365d preservada); foco 13→14.

## L-023 · 2026-09-23 · testes/terminalidade
- **Gatilho**: testar guard que recusa decisão para um **conjunto** de estados terminais (`status != "pendente"`) exercitando só um estado.
- **Erro**: o teste de rejeição da T8 só cobria `status="aplicado"`; os outros terminais (`rejeitado`, `falhou`) passariam mesmo se o guard regredisse, e o `motivo_rejeicao` de um item já rejeitado poderia ser sobrescrito em silêncio.
- **Regra**: quando a guarda cobre um conjunto de estados, parametrize o teste por **cada** estado do conjunto e assevere a não-alteração (`status` inalterado + campo de decisão ainda `None`).
- **Evidência**: self-review T8; `test_rejeitar_item_terminal_recusa` parametrizado em `["rejeitado","aplicado","falhou"]` (+2 testes; foco 71→73).

## L-022 · 2026-09-23 · processo/ADRs
- **Gatilho**: delegar a geração da ADR ao subagente `developer-self-reviewer` sem validar a saída.
- **Erro**: instruí o subagente a aplicar `write-fluid-hybrid-adr`, mas as ADRs T1–T6 saíram com 4 seções — faltava **"O que vem a seguir (Roadmap Imediato)"** em todas e a seção **"Validação de Qualidade e Segurança"** na T3 — divergindo do template; eu não conferi.
- **Regra**: carregue a skill e **gere/valide a ADR você mesmo** (checklist das 5 seções) antes de fechar a task; delegação não substitui a verificação.
- **Evidência**: correção do usuário; PR #55 (`docs/f2-adr-fluido`) alinhou T1–T6.

## L-021 · 2026-09-23 · testes/cobertura
- **Gatilho**: implementar aplicação genérica por `tipo` (mapeamento posicional `_CAMPOS_UPSERT` → assinatura de `upsert`) e testar só um dos tipos.
- **Erro**: a suíte da T7 exercitava `aprovar` apenas em `estoque`; um desalinhamento de ordem em `fornecedores`/`transporte` passaria em silêncio (gravando valores trocados por posição) — o risco de ordem da L-013.
- **Regra**: quando um mapa cobre vários tipos, cada tipo do mapa precisa do seu próprio teste de aplicação; cobertura de um ramo não valida os demais.
- **Evidência**: self-review T7; acrescentados `test_aprovar_aplica_fornecedor` e `test_aprovar_aplica_transporte`.

## L-020 · 2026-09-23 · auditoria/contrato
- **Gatilho**: montar `detalhe` de evento cujo contrato (design/T6) prevê o `valor` truncado.
- **Erro**: em `_finalizar` gravei `item.valor_sugerido` inteiro no `detalhe` de `correcao_aplicada`; no SQLite `String(255)` não é imposto, então um texto sem limite poderia ir ao `detalhe` — contrariando o contrato "valor truncado".
- **Regra**: quando o design diz que um campo do `detalhe` é truncado, trunque explicitamente no call site, sem confiar em constraint de coluna do banco.
- **Evidência**: self-review T7; `_valor_auditavel` com `_LIMITE_VALOR_AUDITORIA = 255` e `test_valor_de_auditoria_e_truncado`.

## L-019 · 2026-09-23 · documentação/auditoria
- **Gatilho**: transcrever para o docstring de um módulo o contrato de um campo (`detalhe` de auditoria) já especificado no design.
- **Erro**: copiei "nunca carrega justificativa/motivo_rejeicao nem PII", mas omiti o qualificador do design "o `valor` é dado operacional de catálogo, **truncado**"; o docstring virou contrato incompleto e deixava ambíguo que `motivo` (FALHOU) é código de falha, não texto livre.
- **Regra**: ao transcrever um contrato do design para docstring, transcreva-o integralmente — inclua os qualificadores (ex.: truncamento) e desambigue campos homônimos — em vez de resumir.
- **Evidência**: self-review T6; `audit/eventos.py` passou a citar `valor` truncado e `motivo` como código de falha.

## L-018 · 2026-09-23 · testes/organização
- **Gatilho**: criar um arquivo de teste com o mesmo basename de um teste já existente em outro subdiretório de `tests/` (sem `__init__.py`).
- **Erro**: criei `tests/correcoes/test_servico.py` clonando o nome de `tests/ingestion/test_servico.py`; a suíte completa falhou na coleta ("import file mismatch") porque o pytest importa ambos como o módulo `test_servico`.
- **Regra**: em `tests/` sem pacotes, use basename único por arquivo (ex.: `test_servico_fila.py`); ao criar um `test_*.py`, confira se o nome já existe em outro diretório.
- **Evidência**: T5; suíte coletava 1 erro e passou (335) após renomear para `tests/correcoes/test_servico_fila.py`.

## L-017 · 2026-09-23 · tipagem
- **Gatilho**: anotar helper que devolve uma de duas formas de valor conforme um ramo (`moda` → textos; numérico → floats).
- **Erro**: declarei `-> list`, apagando a união real; o chamador não enxerga que ora vêm `str`, ora `float`, e a checagem estática não distingue.
- **Regra**: anote a união real (`list[str] | list[float]`) em vez de `list` cru; "lista de qualquer coisa" esconde o contrato de quem consome.
- **Evidência**: self-review T4; `correcoes/sugestoes.py::_valores` passou de `-> list` para `-> list[str] | list[float]`.

## L-016 · 2026-09-23 · domínio/refatoração
- **Gatilho**: refatorar uma função para delegar a um helper de reuso (validação + serialização).
- **Erro**: em `valor_atual` passei `getattr(registro, campo)` como argumento de `serializar` antes de validar o campo; campo desconhecido estourou `AttributeError` em vez do erro de domínio `CampoCorrecaoInvalido`.
- **Regra**: ao extrair helper, preserve a ordem original de avaliação — valide o campo **antes** de avaliar `getattr` (`tipo_campo = natureza(...)`; depois `_serializar(getattr(...))`).
- **Evidência**: T4; `tests/correcoes/test_completude.py::test_campo_desconhecido_recusa` (falhou e passou após o ajuste).

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
