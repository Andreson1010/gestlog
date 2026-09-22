# Lições (memória de erros — projeto gestlog)

> Só erro real, já corrigido e observado; teto ~40 linhas; mais recente no topo.
> Formato: `Gatilho / Erro / Regra / Evidência`. Ver "Loop de auto-melhoria" no `AGENTS.md`.

## L-013 · 2026-09-22 · web/schema
- **Gatilho**: página HTML cujo `<select>`/validação usa um conjunto de valores que já existe como `Literal` no schema JSON.
- **Erro**: redeclarei `_PAPEIS = ("admin", "gestor", "operador")` no router, duplicando a fonte de verdade; ao mudar o domínio, formulário e API divergem em silêncio.
- **Regra**: derive opções e validação de uma única fonte (`get_args(Papel)`), nunca recopie o enum.
- **Evidência**: self-review T6; `admin_ui.py` passou a usar `get_args(Papel)` em vez da tupla local.

## L-012 · 2026-09-22 · html/js
- **Gatilho**: botão com ícone SVG + texto que precisa mudar de rótulo temporariamente (ex.: "Copiar conversa" → "Copiado!").
- **Erro**: usei `botao.textContent = "Copiado!"` e depois restaurei só o texto; `textContent` apaga TODOS os filhos, então o `<svg>` do botão foi destruído na primeira cópia (regressão visual silenciosa, sem teste).
- **Regra**: ao trocar o rótulo de um controle que contém ícone, envolva o texto num `<span data-...>` e altere só o `textContent` desse span — nunca o do container.
- **Evidência**: code review do pente geral; `chat.html` agora tem `[data-rotulo-copiar]` e o JS preserva o SVG.

## L-011 · 2026-09-21 · web/testes
- **Gatilho**: remover da UI um controle/markup que outra camada consome (ex.: botões de feedback do chat).
- **Erro**: rodei só `tests/web/` e esqueci que `tests/acceptance/test_f1_mvp.py` raspava o HTML do chat (`/recomendacoes/<id>/feedback`) para obter o id da recomendação — quebrou após a remoção.
- **Regra**: ao remover/renomear markup, rode a suíte **completa** e prefira buscar ids no banco/repositório em vez de extraí-los do HTML renderizado.
- **Evidência**: `test_cop_aceite_registra_decisao` — agora usa `_recomendacao_do_usuario(fabrica_sync, email)`.

## L-010 · 2026-09-21 · css/templates
- **Gatilho**: reescrever um CSS global que ainda serve páginas não migradas / declarar asset externo por token.
- **Erro**: (a) ao reescrever `app.css` removi `.form-importar select,input` (página `importar` sem estilo) e mantive `.form-chat button` legado que, por especificidade, sobrescreveu `.chat-enviar`; (b) `--font-sans: Inter` sem carregar a fonte.
- **Regra**: ao reescrever CSS global, inventarie TODAS as regras legadas ainda referenciadas por templates e remova/escope as que colidem com os novos componentes; ao nomear um asset num token, carregue-o no `<head>`.
- **Evidência**: code review do PR (HIGH `importar` sem estilo; MEDIUM `.form-chat button` > `.chat-enviar`); `base.html` ganhou Google Fonts (consolida L-008).

## L-009 · 2026-09-21 · web/form
- **Gatilho**: rota web com `Form()` obrigatório que deve **reexibir o formulário** quando o input é inválido.
- **Erro**: `Annotated[str, Form()]` com valor vazio vira `None` no FastAPI → responde **422 JSON** ("missing"), sem cair no handler que re-renderiza o HTML.
- **Regra**: dê default `""` aos campos `Form()` e deixe o schema Pydantic rejeitar; assim todo input inválido passa pelo mesmo caminho de erro renderizado.
- **Evidência**: `tests/web/test_cadastro.py::test_cadastro_nome_empresa_vazio_recusa` (422 antes, 400 após).

## L-007 · 2026-09-21 · grafo/testes
- **Gatilho**: endurecer um fluxo (guarda anti-loop) e cobrir a correção com teste de regressão.
- **Erro**: forçar `FINISH` em toda `AIMessage` quebrou o roteamento multi-especialista; o teste da guarda só afirmava `next == "FINISH"`, que passava mesmo sem ela.
- **Regra**: modele o requisito real (rastrear `especialistas_visitados` e barrar só a **repetição**) e afirme o efeito **exclusivo** da correção; rode a suíte completa.
- **Evidência**: `test_graph_encerra_sem_reencaminhar_apos_especialista` (passava sem a guarda); golden set quebrou com o forcing.

## L-004 · 2026-09-21 · opencode (fluxo + plugin) — consolida L-002/L-003
- **Gatilho**: tornar um artefato obrigatório num passo de fluxo multiarquivo; decidir gate vermelho→verde por regex no plugin `self-learning`.
- **Erro**: (a) adicionei "Lesson Capture" ao `developer-self-reviewer`/skills mas não ao `feature-factory` (fase 5.5), então o Persistence Gate mutava arquivo "inesperado"; (b) `\b\d+\s+failed\b` casava "0 failed" e `\berror\b` texto benigno, e `failedBySession` crescia sem limite.
- **Regra**: ao mudar o que um passo produz, atualize TODOS os lugares que o enumeram (skill, gate, agent); com exit code decida só por ele, senão exija `[1-9]\d*`; cape sessões/falhas com evict LRU.
- **Evidência**: `feature-factory/SKILL.md` fase 5.5; `.opencode/plugin/self-learning.ts` (`FAIL`/`PASS`, `recordFailure`).
