# ADR: memoria-auto-melhoria

## 1. Context & Goal

O agente erra, corrige e **esquece**. Sem uma memória persistente, o mesmo erro
(um gate quebrado, um achado de review, uma correção do usuário) volta a ocorrer
na próxima sessão, porque o contexto da conversa não sobrevive a ela. Esta chore
introduz uma memória de auto-melhoria **de um único tier, só deste projeto**:
`.opencode/LESSONS.md`, no formato `Gatilho / Erro / Regra / Evidência`, id
sequencial `L-00N`, mais recente no topo, teto de ~40 linhas, alimentada **apenas
por erro real, já corrigido e observado**.

O desafio não é armazenar texto — é fazer a **captura ser automática** sem depender
de o usuário lembrar de invocar `/lesson`, sem poluir config global e sem que
qualquer mecanismo de captura quebre as ferramentas do agente. A ideia original de
dois tiers (global + projeto) foi revertida a pedido do usuário, o que fixou o
escopo: **nada em config global**.

## 2. Architectural Decisions

- **Decisão 1: memória em arquivo único do projeto, carregada via `instructions`.**
  - **Justificativa:** `opencode.json` passa `instructions: ["AGENTS.md",
    ".opencode/LESSONS.md"]`, então a memória entra no contexto **toda sessão** sem
    ação explícita. Um único tier (projeto) evita vazar lições específicas do
    gestlog para repositórios não relacionados — o que um arquivo global faria. O
    conteúdo é markdown versionado no repo, revisável em PR como qualquer outro
    documento.

- **Decisão 2: captura automática em três superfícies complementares.**
  - **Justificativa:** nenhuma superfície sozinha cobre todos os momentos.
    `AGENTS.md` (seção "Loop de auto-melhoria") é a **regra declarativa** sempre em
    contexto; os checkpoints em `build-with-tests`, `code-reviewer` e
    `developer-self-reviewer` ancoram a gravação nos fluxos onde o erro costuma
    aparecer; o plugin `self-learning.ts` é o **gatilho reativo**, que observa o
    bash e só lembra quando um gate vermelho fica verde na mesma sessão. `/lesson`
    fica como override manual e `/end` como ponto de consolidação/dedup.

- **Decisão 3: no plugin, o exit code é a fonte de verdade; regex de texto é só
  fallback.**
  - **Justificativa:** exit code é autoritativo e imune a falsos positivos de
    sumário — ex.: "0 failed" ou "1 failed, 2 passed" que casam heurística de
    texto. O texto só é consultado quando `metadata` não traz `exitCode`/`exit`.
    Assim `isFail`/`isPass` viram ternários simétricos (`hasCode ? code !== 0 :
    FAIL.test(text)` e `hasCode ? code === 0 : PASS.test(text) && !FAIL.test(text)`),
    removendo a assimetria anterior em que o ramo sem código misturava PASS e FAIL.

- **Decisão 4: estado do gate keyed por `sessionID` + comando trimado.**
  - **Justificativa:** escopar por sessão impede que um gate vermelho de uma sessão
    antiga dispare aviso em outra; a chave pelo comando exato torna o sinal
    **conservador** — o lembrete só aparece quando **o mesmo comando** foi vermelho
    e depois verde, que é o caso de "conserto do próprio erro". Dois comandos
    distintos (`uv run pytest` × `uv run pytest tests/x --no-cov`) são chaves
    distintas: não colidem, e a troca de comando simplesmente não dispara o
    lembrete (falso negativo preferível a ruído).

- **Decisão 5: o hook nunca lança e nunca bloqueia.**
  - **Justificativa:** todo o corpo de `tool.execute.after` está em `try/catch` e o
    aviso é **anexado a `output.output`** (informativo), não um erro. Um bug no
    lembrete jamais pode quebrar a ferramenta `bash` — requisito de robustez do
    plugin.

- **Decisão 6: a memória de sessões é limitada.**
  - **Justificativa:** o módulo do plugin vive enquanto o processo do opencode
    viver. Sem poda, `failedBySession` cresceria indefinidamente. O estado é
    limitado em duas dimensões: cada sessão tem no máximo
    `MAX_FAILURES_PER_SESSION` comandos falhos (os mais antigos caem) e o total de
    sessões é capado com poda (`MAX_SESSIONS`), reordenando a sessão tocada para o
    fim — ou seja, evicção **LRU** (a menos recentemente falha sai primeiro), não
    FIFO por primeira aparição. Limpar o `Set` vazio remove sessões já resolvidas.

## 3. Trade-offs & Compromises

- **Heurística de texto é imperfeita.** Mesmo com exit code primário, comandos sem
  `metadata` de código caem na regex. Aceitável porque o lembrete é **advisory**:
  um falso negativo perde um lembrete; um falso positivo custa uma frase de
  contexto, não uma ação errada.
- **Chave exata por comando perde red→green entre invocações diferentes** (teste
  focado falha, suíte inteira passa). Trocado deliberadamente por menos ruído —
  alinhado ao princípio de só gravar erro real e observado.
- **Memória carregada em todo contexto custa tokens.** O teto de ~40 linhas e a
  consolidação no `/end` limitam o custo; é o preço de não depender de invocação
  manual.
- **A consolidação depende de o agente seguir a instrução**, não é imposta por
  código. O `/end` descreve o procedimento (dedup + poda), mas nada o força
  tecnicamente.

## 4. Known Limitations

- **O plugin só observa a ferramenta `bash`.** Correções feitas por edição/outras
  ferramentas não são detectadas pelo gatilho reativo; dependem da regra do
  `AGENTS.md`/checkpoints.
- **Depende de `output.metadata.exitCode`/`exit`.** Se uma versão do opencode não
  fornecer o código de saída, a detecção cai na regex de texto e herda suas
  limitações.
- **Escopo é só deste projeto, por decisão explícita.** A ideia de tier global foi
  revertida; replicar para outros repos exige copiar o arquivo/plugin.
- **Exige reiniciar o opencode** para `opencode.json` e o plugin novos valerem —
  config/plugin não são hot-reloaded.
- **Sem teste automatizado do plugin TS.** O repo não tem harness JS e o CI
  (`black`/`ruff`/`pytest`) não roda `bun`; um teste que ninguém executa daria falsa
  confiança, então a verificação é transpile (`bun build --no-bundle`) + typecheck
  (`tsc --noEmit`), ambos verdes. Extrair as funções puras e cobrir com `bun:test` é
  follow-up quando o repo tiver harness JS.
- **Sem impacto na suíte Python.** Nenhum arquivo `.py` foi alterado; a suíte
  permanece 248 passed / 98,26% (não reexecutada neste self-review, por não haver
  mudança de código Python).

## Achados corrigidos no self-review

- **Regex de gate casava contagem zero e "error" solto.** `\b\d+\s+failed\b`
  casava "0 failed" e `\berror\b` casava texto benigno, podendo marcar falha em
  execução sem falhas (e os ramos `isFail`/`isPass` eram assimétricos sem exit
  code). Corrigido para exigir contagem `[1-9]\d*` em `failed`/`passed`/`error(s)`,
  remover "error" solto e decidir pelo exit code quando presente.
- **`failedBySession` crescia sem limite.** Adicionada a remoção da entrada da
  sessão quando o `Set` esvazia e poda FIFO com `MAX_SESSIONS = 100`.
- **`GATE` casava `pnpm`/`yarn`/`npm` genéricos** (ex.: `pnpm install`). Restringido
  a `(npm|pnpm|yarn) (run)? (test|lint|typecheck)` para reduzir ruído.
- **Sem achados de segurança.** Nenhum segredo envolvido; o plugin apenas lê
  comando/saída e anexa texto fixo, sem executar nada nem persistir dados.

## Achados corrigidos no code review

- **`feature-factory` (fase 5.5) não citava `LESSONS.md`.** Ao tornar a lição um
  artefato obrigatório do self-review, o `expected_changes` do Persistence Gate e a
  lista "What it produces" ficaram desatualizados. Corrigido para incluir
  `.opencode/LESSONS.md` — senão um self-review correto mutaria um arquivo
  "inesperado" pelo gate.
- **Cada `Set` de sessão crescia sem limite.** `MAX_SESSIONS` limitava o nº de
  sessões, mas muitos comandos falhos distintos numa mesma sessão cresciam o `Set`.
  Adicionado `MAX_FAILURES_PER_SESSION`.
- **Evicção por primeira aparição, não LRU.** `Map.set` num id existente não
  reordena; uma sessão antiga ainda ativa poderia ser evictada. Agora a sessão
  tocada vai para o fim (`delete` + `set`), tornando a poda LRU.
