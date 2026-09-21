# Lições (memória de erros — projeto gestlog)

> Só erro real, já corrigido e observado; teto ~40 linhas; mais recente no topo.
> Formato: `Gatilho / Erro / Regra / Evidência`. Ver "Loop de auto-melhoria" no `AGENTS.md`.

## L-009 · 2026-09-21 · web/form
- **Gatilho**: rota web com `Form()` obrigatório que deve **reexibir o formulário** quando o input é inválido.
- **Erro**: `Annotated[str, Form()]` com valor vazio é convertido a `None` pelo FastAPI → responde **422 JSON** ("missing"), sem cair no handler que re-renderiza o HTML.
- **Regra**: dê default `""` aos campos `Form()` e deixe o schema Pydantic rejeitar; assim todo input inválido passa pelo mesmo caminho de erro renderizado.
- **Evidência**: `tests/web/test_cadastro.py::test_cadastro_nome_empresa_invalido_recusa` (422 antes, 400 após).

## L-008 · 2026-09-21 · css/templates
- **Gatilho**: entregar estilo que referencia um asset (fonte) por design token.
- **Erro**: `tokens.css` declarou `--font-sans: Inter, …` mas nenhum `@font-face`/link carregava a Inter; em máquina sem a fonte o requisito ("Inter font") ficava silenciosamente não cumprido.
- **Regra**: ao nomear um asset externo num token, carregue-o (link/`@font-face`) e confirme que o `base.html` o referencia no `<head>`.
- **Evidência**: `base.html` ganhou preconnect + stylesheet Google Fonts (Inter).

## L-007 · 2026-09-21 · grafo/testes
- **Gatilho**: endurecer um fluxo (guarda anti-loop) e cobrir a correção com teste de regressão.
- **Erro**: forçar `FINISH` em toda `AIMessage` quebrou o roteamento multi-especialista; o teste da guarda só afirmava `next == "FINISH"`, que passava mesmo sem ela.
- **Regra**: modele o requisito real (rastrear `especialistas_visitados` e barrar só a **repetição**) e afirme o efeito **exclusivo** da correção (`especialistas_visitados == ["estoque"]`); rode a suíte completa.
- **Evidência**: `test_graph_encerra_sem_reencaminhar_apos_especialista` (passava sem a guarda); `test_answer_soma_tokens_de_multiplos_especialistas`/golden set quebraram com o forcing (consolida L-006/L-007).

## L-005 · 2026-09-21 · shell/opencode
- **Gatilho**: rodar comando longo ou subir daemon a partir da shell do opencode (Windows/pwsh).
- **Erro**: `cmd | Select-Object -Last N` bufferiza e a tela fica muda; `Start-Process -RedirectStandardOutput/Error` de um daemon faz o filho herdar o pipe e a tool call trava (EOF nunca chega; PID órfão segurando o log).
- **Regra**: não filtrar saída de comando longo (sem pipe ou redirect p/ arquivo); lançar daemon via `Invoke-CimMethod Win32_Process.Create` e esperar pela porta (`Get-NetTCPConnection -LocalPort`) em loop, nunca `Start-Sleep` fixo.
- **Evidência**: `pytest | Select-Object -Last 15` mudo por 52 s; PID órfão 22660 segurando `ollama.err.log` → WMI PID 22684, endpoint 11434 OK.

## L-004 · 2026-09-21 · fluxos/opencode
- **Gatilho**: tornar um artefato obrigatório num passo de fluxo multiarquivo.
- **Erro**: adicionei "Lesson Capture" ao `developer-self-reviewer` e às skills, mas não ao `feature-factory` (fase 5.5): o `expected_changes` do Persistence Gate não citava `.opencode/LESSONS.md`, então um self-review correto mutaria um arquivo "inesperado".
- **Regra**: ao mudar o que um passo produz, atualizar TODOS os lugares que o enumeram (skill do orquestrador, gate de persistência, agent).
- **Evidência**: `.opencode/skills/feature-factory/SKILL.md` — fase 5.5.

## L-003 · 2026-09-21 · plugin/opencode
- **Gatilho**: decidir gate vermelho→verde por regex e manter estado por sessão no plugin `self-learning`.
- **Erro**: `\b\d+\s+failed\b` casava "0 failed" e `\berror\b` texto benigno (ramos assimétricos sem exit code); `failedBySession` crescia sem limite.
- **Regra**: com exit code decida só por ele, senão exija `[1-9]\d*` (nunca "error" solto); capar sessões/falhas e evictar LRU, apagando a sessão ao esvaziar.
- **Evidência**: `.opencode/plugin/self-learning.ts` — `FAIL`/`PASS`, `recordFailure` (consolida L-002/L-003).
