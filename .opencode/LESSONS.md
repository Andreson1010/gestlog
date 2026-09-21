# Lições (memória de erros — projeto gestlog)

> Memória de correção de erros do agente para **este repositório**. Carregada em
> toda sessão via `instructions` em `opencode.json`. Só entra lição nascida de um
> **erro real e já corrigido**. Teto: ~40 linhas.
> Formato: `Gatilho / Erro / Regra / Evidência`. Mais recente no topo.
> Ver o "Loop de auto-melhoria" no `AGENTS.md`.

## L-001 · 2026-09-20 · shell/pwsh

- **Gatilho**: rodar comando longo (download, suíte de testes) e querer ver só o fim.
- **Erro**: `cmd | Select-Object -Last N` bufferiza toda a saída e a tela fica
  muda até o comando terminar — parece travado e esconde progresso.
- **Regra**: não filtrar saída de comando longo; rodar sem pipe (a saída flui) ou
  redirecionar para arquivo e ler depois.
- **Evidência**: `ollama pull qwen2.5:7b` (4,7 GB) sem output por minutos;
  `uv run pytest | Select-Object -Last 15` mudo por 52 s.
