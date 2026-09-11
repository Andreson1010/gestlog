---
description: Retoma a sessão anterior carregando o handoff persistido em .opencode/CONTEXT.md (gravado por /end).
agent: build
---

Leia `.opencode/CONTEXT.md` — o handoff da sessão anterior, gravado pelo comando
`/end` — e use-o como memória persistente desta sessão.

Estado do repositório agora (confira contra o que o arquivo afirma):

!`git status --short`
!`git log --oneline -10`
!`git worktree list`

Passos:

1. Leia `.opencode/CONTEXT.md` inteiro.
2. Valide o "Estado atual" contra o repositório acima. Se algo divergir, corrija
   o arquivo antes de agir.
3. Se houver bloqueio ou trabalho parcial (seções "Próximos passos", "WIP local"
   ou TODOs em aberto), retome exatamente de onde parou — não refaça o que já
   está marcado como concluído.
4. Responda em poucas linhas: estado atual, o que ficou pendente e a próxima
   ação sugerida. Se houver mais de um caminho, pergunte por qual seguir.

Mantenha o arquivo atualizado sempre que uma decisão ou próximo passo mudar.
