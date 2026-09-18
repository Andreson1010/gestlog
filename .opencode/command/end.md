---
description: Encerra a sessão gravando um handoff persistente em .opencode/CONTEXT.md (estado, decisões, artefatos do graphify e documentos de projeto).
agent: build
---

Encerre a sessão persistindo o estado para a próxima. Atualize (ou crie)
`.opencode/CONTEXT.md`; ele é lido pelo comando `/start` na próxima sessão.

Colete os dados antes de escrever.

**1. Git / estado** — execute e registre:

!`git status --short`
!`git log --oneline -10`
!`git worktree list`

Anote também a branch atual e o HEAD (hash).

**2. Graphify** (se o MCP `graphify` estiver disponível) — chame as ferramentas e
registre os números reais, priorizando os módulos tocados nesta sessão:

- `graphify_graph_stats` → nº de nós, arestas, comunidades.
- `graphify_god_nodes` com `top_n=10` → abstrações mais conectadas.
- `graphify_query_graph` para os subsistemas alterados → comunidades afetadas.

Se o MCP não estiver acessível, escreva explicitamente "graphify indisponível"
— não invente valores.

**3. Documentos de projeto** — liste o que existe e o que mudou nesta sessão:
`docs/specs/`, `docs/`, `AGENTS.md`, `README.md`, `.opencode/skills/`. Aponte
caminhos concretos.

Estrutura do arquivo (substitua o conteúdo antigo; mantenha o histórico curto e
por sessão, mais recente no topo):

```markdown
# Contexto da Sessão — <assunto>
> Handoff persistente. `/end` grava, `/start` lê. Última atualização: <data>.
> Branch: <branch> · HEAD: <hash>

## Estado atual
- ...

## O que foi feito nesta sessão
- ...

## Decisões e regras (não esquecer)
- ...

## Próximos passos / bloqueios
1. ...

## WIP local (não commitado)
- ...

## Artefatos do graphify
- Nós: N · Arestas: N · Comunidades: N
- God nodes: ...
- Comunidades afetadas: ...

## Documentos de projeto relevantes
- `docs/specs/...`, `docs/...`, ...

---
# Histórico (sessões anteriores, resumido)
```

Regras:

- Factual e curto; nada de despejar o transcript inteiro.
- Marque explicitamente **concluído** vs. **pendente**.
- Se não verificou algo, escreva "não verificado" — nunca invente.
- Ao final, mostre um resumo do que foi gravado e onde.
