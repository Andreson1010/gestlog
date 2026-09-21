# Lições (memória de erros — projeto gestlog)

> Só erro real, já corrigido e observado; teto ~40 linhas; mais recente no topo.
> Formato: `Gatilho / Erro / Regra / Evidência`. Ver "Loop de auto-melhoria" no `AGENTS.md`.

## L-007 · 2026-09-21 · testes/grafo
- **Gatilho**: escrever teste de regressão para uma guarda que encerra/trunca um fluxo.
- **Erro**: o teste do grafo só afirmava `next == "FINISH"`; com a fila de rotas esgotada o resultado seria o mesmo **sem** a guarda — passava mesmo sem a correção.
- **Regra**: afirme o efeito observável **exclusivo** da correção (aqui `especialistas_visitados == ["estoque"]`), não um estado final que o caminho sem correção também produz.
- **Evidência**: `tests/test_graph.py::test_graph_encerra_sem_reencaminhar_apos_especialista` (passava sem a guarda).

## L-006 · 2026-09-21 · grafo/opencode
- **Gatilho**: endurecer um fluxo (guarda determinística) para matar um loop/estouro.
- **Erro**: para corrigir o loop do supervisor, forcei `FINISH` sempre que a última mensagem era `AIMessage`, quebrando o roteamento **multi-especialista** (5 testes: tokens somados + golden set).
- **Regra**: modele o requisito real (rastrear `especialistas_visitados` e só barrar a **repetição**); rode a suíte completa, não só o arquivo tocado.
- **Evidência**: `tests/copilot/test_service.py::test_answer_soma_tokens_de_multiplos_especialistas`, `tests/evaluation/test_golden.py`.

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
- **Gatilho**: manter estado por sessão em plugin de longa duração.
- **Erro**: `failedBySession` (e cada `Set`) crescia sem limite enquanto o processo vivesse; a poda era por primeira aparição, não por uso.
- **Regra**: apagar a sessão ao esvaziar o `Set`; capar sessões (`MAX_SESSIONS`) e falhas por sessão (`MAX_FAILURES_PER_SESSION`); reordenar a sessão tocada ao fim para evicção LRU.
- **Evidência**: `.opencode/plugin/self-learning.ts` — `recordFailure`.

## L-002 · 2026-09-21 · plugin/opencode
- **Gatilho**: decidir gate vermelho→verde por regex no plugin.
- **Erro**: `\b\d+\s+failed\b` casava "0 failed" e `\berror\b` texto benigno; os ramos `isFail`/`isPass` eram assimétricos sem exit code.
- **Regra**: exigir contagem `[1-9]\d*`, não casar "error" solto; com exit code, decidir só por ele.
- **Evidência**: `.opencode/plugin/self-learning.ts` — `FAIL`/`PASS` e os ternários.
