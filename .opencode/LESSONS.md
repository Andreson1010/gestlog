# Lições (memória de erros — projeto gestlog)

> Só erro real, já corrigido e observado; teto ~40 linhas; mais recente no topo.
> Formato: `Gatilho / Erro / Regra / Evidência`. Ver "Loop de auto-melhoria" no `AGENTS.md`.

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

## L-001 · 2026-09-20 · shell/pwsh

- **Gatilho**: rodar comando longo (download, suíte) e querer ver só o fim.
- **Erro**: `cmd | Select-Object -Last N` bufferiza tudo e a tela fica muda até terminar — parece travado e esconde progresso.
- **Regra**: não filtrar saída de comando longo; rodar sem pipe ou redirecionar para arquivo e ler depois.
- **Evidência**: `ollama pull qwen2.5:7b` sem output por minutos; `pytest | Select-Object -Last 15` mudo por 52 s.
