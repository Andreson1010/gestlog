# Lições (memória de erros — projeto gestlog)

> Só erro real, já corrigido e observado; teto ~40 linhas; mais recente no topo.
> Formato: `Gatilho / Erro / Regra / Evidência`. Ver "Loop de auto-melhoria" no `AGENTS.md`.

## L-006 · 2026-09-21 · grafo/opencode

- **Gatilho**: endurecer um fluxo (guarda determinística) para matar um loop/estouro.
- **Erro**: para corrigir o loop do supervisor, forcei `FINISH` sempre que a última mensagem era `AIMessage`, encurtando o fluxo e quebrando o roteamento **multi-especialista** (5 testes falharam: tokens somados de 2 especialistas e o golden set).
- **Regra**: modele o requisito real (rastrear `especialistas_visitados` e só barrar a **repetição**) em vez de truncar o fluxo; rode a suíte completa, não só os testes do arquivo tocado.
- **Evidência**: `tests/copilot/test_service.py::test_answer_soma_tokens_de_multiplos_especialistas`, `tests/evaluation/test_golden.py`.

## L-005 · 2026-09-21 · shell/opencode

- **Gatilho**: rodar comando longo ou subir daemon a partir da shell do opencode (Windows/pwsh).
- **Erro**: (a) `cmd | Select-Object -Last N` bufferiza tudo e a tela fica muda até terminar; (b) `Start-Process -RedirectStandardOutput/Error` de um daemon faz o filho herdar os handles do pipe e a tool call trava (EOF nunca chega; PID órfão segurando o log).
- **Regra**: não filtrar saída de comando longo (rodar sem pipe ou redirecionar para arquivo); lançar daemon via `Invoke-CimMethod Win32_Process.Create` (sem herdar stdio) e esperar pela porta (`Get-NetTCPConnection -LocalPort`) em loop, nunca `Start-Sleep` fixo.
- **Evidência**: `pytest | Select-Object -Last 15` mudo por 52 s; PID órfão 22660 segurando `ollama.err.log` → WMI PID 22684, endpoint 11434 OK.

## L-004 · 2026-09-21 · fluxos/opencode

- **Gatilho**: tornar um artefato obrigatório num passo de fluxo multiarquivo.
- **Erro**: adicionei "Lesson Capture" ao `developer-self-reviewer` e às skills, mas não ao `feature-factory` (fase 5.5): o `expected_changes` do Persistence Gate não citava `.opencode/LESSONS.md`, então um self-review correto mutaria um arquivo "inesperado" pelo gate.
- **Regra**: ao mudar o que um passo produz, atualizar TODOS os lugares que o enumeram (skill do orquestrador, gate de persistência, agent).
- **Evidência**: `.opencode/skills/feature-factory/SKILL.md` — fase 5.5.

## L-003 · 2026-09-21 · plugin/opencode

- **Gatilho**: manter estado por sessão em plugin de longa duração.
- **Erro**: `failedBySession` (e cada `Set`) crescia sem limite enquanto o processo do opencode vivesse; a poda era por primeira aparição, não por uso.
- **Regra**: apagar a sessão ao esvaziar o `Set`; capar sessões (`MAX_SESSIONS`) e falhas por sessão (`MAX_FAILURES_PER_SESSION`); reordenar a sessão tocada ao fim para evicção LRU.
- **Evidência**: `.opencode/plugin/self-learning.ts` — `recordFailure`.

## L-002 · 2026-09-21 · plugin/opencode

- **Gatilho**: decidir gate vermelho→verde por regex no plugin.
- **Erro**: `\b\d+\s+failed\b` casava "0 failed" e `\berror\b` texto benigno; os ramos `isFail`/`isPass` eram assimétricos sem exit code.
- **Regra**: exigir contagem `[1-9]\d*`, não casar "error" solto; com exit code, decidir só por ele.
- **Evidência**: `.opencode/plugin/self-learning.ts` — `FAIL`/`PASS` e os ternários.
