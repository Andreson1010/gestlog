---
description: Override manual — registra uma lição em .opencode/LESSONS.md no formato Gatilho/Erro/Regra/Evidência. Normalmente a gravação é automática (ver "Loop de auto-melhoria" no AGENTS.md).
agent: build
---

Override manual do loop de auto-melhoria: registre uma lição de correção de erro na
memória persistente. O insumo do usuário (se houver) vem em `$ARGUMENTS`.

> Normalmente isso **não** precisa ser invocado: o agente grava sozinho ao corrigir
> um erro (teste vermelho→verde, achado de review/débito, correção do usuário) e o
> plugin `self-learning` injeta o lembrete nesses momentos. Use `/lesson` só quando
> a gravação automática não tiver acontecido.

Passos:

1. **Alvo**: `.opencode/LESSONS.md` (único tier, deste projeto).
2. **Leia** o arquivo antes de editar.
3. **Anexe uma entrada** logo abaixo do cabeçalho/notas, no topo da lista (mais
   recente primeiro), com o próximo id sequencial:
   ```markdown
   ## L-00N · <AAAA-MM-DD> · <tema>
   - **Gatilho**: <quando isso acontece>
   - **Erro**: <o que foi feito de errado>
   - **Regra**: <como proceder corretamente da próxima vez>
   - **Evidência**: <comando/arquivo que comprova o erro>
   ```
4. **Valide o rigor**: só registre erro **real, já corrigido e observado**. Se o
   insumo for genérico, hipotético ou não verificado, recuse e explique.
5. **Respeite o teto** de ~40 linhas: se estourar, consolide/deduplique entradas
   antigas obsoletas antes de adicionar.
6. Ao final, informe qual arquivo e qual id foram gravados.
