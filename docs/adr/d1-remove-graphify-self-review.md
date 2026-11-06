# ADR: d1-remove-graphify

## 1. Contexto & Objetivo

O `opencode.json` carregava um servidor MCP local chamado `graphify`, apontado
para o grafo gerado no projeto **medasist** (`<projeto-externo>/graphify-out/
graph.json`), não no gestlog. Configuração herdada de quando o MCP foi
experimentado, ela nunca serviu a este repositório: o caminho aponta para um
arquivo de outro projeto, o MCP falhava na inicialização a cada sessão
(indisponível), e os nós/arestas nunca puderam ser verificados aqui pelo MCP
— o gestlog tem, por outro lado, um diretório local `graphify-out/` (grafo
gerado em 2026-09-21, ignorado no `.gitignore` desde o #41), mas nenhum
servidor apontava para ele. O custo era duplo e silencioso:
ruído de erro na inicialização de **todas** as sessões (não só as do projeto
medasist) e um vínculo de configuração com um repositório externo que pode
mudar ou desaparecer sem aviso — uma dependência fantasma de warehouse para
fora do projeto. Nenhum código, teste ou script do gestlog referencia o
graphify; não havia nada a migrar, apenas a desligar.

O objetivo da D1 é simples e de fronteira estreita: remover o bloco `graphify`
do `opencode.json`, eliminando referências pendentes de baixo custo no mesmo
fôlego, sem tocar em qualquer arquivo de código (o WIP de D2–D7 desta sessão
fica intocado e separado).

## 2. Decisões de Arquitetura

**1. Remoção limpa do bloco em vez de desativar com `enabled: false`**

A config antiga de servidores MCP oferece a saída "fácil" de manter o
declarado e marcar `"enabled": false`. Foi rejeitada com propósito principal
manter o arquivo honesto para o próximo leitor: um servidor desativado que
aponta para um caminho de outro projeto continua espalhando a mentira de que
o gestlog tem um grafo próprio, e o bloco morto continuaria sendo lido,
copiado e "reparado" nas próximas passadas de config. A remoção física das 8
linhas deixa o dicionário `mcp` com apenas os três servidores ativos e
reais — `playwright`, `chrome-devtools` e `context7` —, todos rodando via
`npx` e sem acoplamento com outros repositórios. Há ainda um ganho de
privacidade: o caminho antigo expunha a organização local de diretórios do
autor em arquivo commitado; a config ativa deixa de expor essa estrutura
(embora o histórico do git preserve os commits antigos — a correção é
aditiva, não de reescrita).

**2. Escopo fechado: só config e ADR**

A D1 deliberadamente não tocou código, migrações ou testes. A verificação de
que nada quebra é por ausência de dependências: o grep por `graphify` no
repositório localiza apenas (a) a regra intencional do `.gitignore` para o
artefato gerado localmente, (b) o comando
`/end` do opencode (que já trata o MCP como opcional, com fallback explícito
de escrever "graphify indisponível" quando ele não responde) e (c) os
handoffs da própria sessão. Nenhum dos três é importado por `src/` ou
`tests/`; nenhum teste lê o `opencode.json` (confirmado por busca — por isso
o gate pytest não é exigido para este PR).

**3. Regra do `.gitignore` para `graphify-out/` permanece (achado do code review)**

O self-review chegou a remover o bloco `# graphify (grafo gerado)` /
`graphify-out/` do `.gitignore` sob a premissa de que a regra era morta — o
MCP apontava para o medasist. A revisão por pares desmentiu a premissa: o
diretório `graphify-out/` **existe no gestlog** (grafo gerado em 2026-09-21 a
partir do commit `5845358f`, 159 arquivos), e a regra foi adicionada
propositadamente pelo próprio #41 para ignorar esse artefato. A remoção
desprotegia um artefato real — passando a expô-lo a um `git add .` e fazendo
ferramentas de busca respeitantes de `.gitignore` varrerem o `graph.json`
gerado (megabytes) no workspace. A regra foi **restaurada**: é proteção viva
e coerente com o estado atual (grafo gerado localmente, sem servidor MCP na
config). Lição metodológica registrada: busca de referências que respeita
`.gitignore` (ripgrep) é cega justamente ao artefato cuja regra está sendo
avaliada — verificar estado do filesystem com `git status --ignored` ou
listagem direta antes de declarar um caminho inexistente.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **O `/end` continua mencionando o graphify:** o comando
  `.opencode/command/end.md` ainda descreve como consumir o MCP do graphify
  (com guarda "se estiver disponível" e fallback documentado). A ação é
  inofensiva hoje — sem o servidor na config, o condicional simplesmente
  nunca executa, e o comando registra "indisponível". Corrigir o comando é
  tarefa de higiene do workspace do opencode, não da config deste PR; ficou
  registrada para a limpeza futura em vez de expandir o escopo de um commit
  de uma linha de verdade funcional.
* **Sem `pytest`/gate de cobertura no PR:** o diff é JSON de configuração e
  o `.gitignore`; a suíte não carrega `opencode.json` (verificado por busca
  no `tests/`). A validação executada aqui foi parse estrutural do JSON com
  `ConvertFrom-Json` (válido, `mcp` com exatamente 3 servidores, sem chave
  residual `graphify`).
* **História de config não é reescrita:** o commit que introduziu o vínculo
  com o medasist permanece no histórico; a correção é aditiva (commits
  novos), em linha com a regra do AGENTS.md de nunca reescrever branches
  compartilhadas.

## 4. O que vem a seguir (Roadmap Imediato)

* **Commit/PR do trabalho D2–D7:** o restante das dívidas D2–D7 desta sessão
  (`String(4000)` → `Text` com migração, AD-019 de ordenação monotônica +
  botões no turno, AD-015 de rate limiting + convites, empresa ativa via
  cookie, workflow de evals) segue como WIP local; o CONTEXT.md sugere dois
  PRs coesos (`D2+D3+D4`, `D5+D6+D7`). Nada disso entra neste PR.
* **Higiene do `/end` (baixa):** remover a seção de instruções do graphify
  de `.opencode/command/end.md` quando a limpeza do workspace do opencode
  for feita, consolidando a decisão da D1 também na ferramenta.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio/privacidade:** nenhuma segredo ou credencial no
  diff removido/atualizado; o único dado sensível relevante era o caminho do
  host revelando a organização de diretórios do autor (e o vínculo com
  outro projeto), eliminado pela própria remoção. Os handoffs da sessão
  (`.opencode/CONTEXT.md`, `.opencode/LESSONS.md`) e o PDF
  `docs/business/KipperDev-Guia-Seguranca-Vibe-Coding.pdf` permanecem fora
  do PR, como definido.
* **Cobertura e testes automatizados:** não aplicável por natureza do diff —
  não há código Python; nenhum teste do repositório lê a config do opencode
  (busca confirmada em `tests/`, incluindo `conftest.py`).
* **Padrões de qualidade:** `opencode.json` parseado com `ConvertFrom-Json`
  sem erro, chave `mcp` final = `playwright`, `chrome-devtools`, `context7`.
  Mensagem de commit em português imperativo
  (`refactor(config): remove MCP graphify que aponta para projeto externo`),
  diff mínimo; commit original toca um único arquivo funcional
  (`opencode.json`), com os ajustes de documentação em commits subsequentes.

## Achados do review (self-review + code review independente)

* **Regra de `.gitignore` para `graphify-out/` erroneamente removida
  (HIGH, code review independente):** o self-review a julgou morta por causa
  da premissa "não há `graphify-out/` aqui" — falsa; o diretório existe (grafo
  do próprio gestlog, gerado em 2026-09-21, ignorado por design desde o
  #41). Restaurado no commit de correção; a ADR documenta a premissa
  corrigida e a lição metodológica (busca respeitante de `.gitignore` é cega
  ao artefato ignorado).
* **Sem achados** de segurança, quebra de referência ou validade de JSON no
  diff da config. Referências residuais reportadas (não corrigidas em D1):
  `.opencode/command/end.md` (guarda condicional, inofensivo) e os handoffs
  da sessão (`.opencode/CONTEXT.md`, `.opencode/LESSONS.md`), fora do
  escopo de commit por definição.
