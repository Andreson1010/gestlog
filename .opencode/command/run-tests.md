---
description: Executa a suíte de testes do projeto com o gate de cobertura.
---

Rode a suíte completa com o gate de cobertura do projeto (comandos definidos no
`AGENTS.md`):

```bash
uv run pytest
```

Para um arquivo ou teste específico — use `--no-cov` para não disparar o gate de
cobertura:

```bash
uv run pytest tests/$ARGUMENTS --no-cov -v
```
