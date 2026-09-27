# ADR: f2-t08-rejeicao

## 1. Contexto & Objetivo

A T7 fechou o primeiro metade do núcleo HITL: uma pessoa autorizada aprova um item da
fila e a correção é escrita no cadastro, com autoria e auditoria. Faltava a outra
metade — a **recusa deliberada**. Um aprovador nem sempre quer aplicar a sugestão: o
valor sugerido pode estar inadequado, a regra de negócio pode não se aplicar àquele
cadastro, ou o item pode ter vindo "sem sugestão" e não haver nada a aprovar. Em todos
esses casos, o correto não é ignorar o item, e sim **encerrá-lo com uma justificativa
registrada**, para que a decisão fique rastreável e o item não reapareça na fila.

A T8 entrega `CorrectionService.rejeitar(item_id, user_id, papel, justificativa)` em
`src/gestlog/correcoes/servico.py`, dando suporte à história de fila HITL (APR-03/04/05)
e fechando o par de decisões que a especificação P1 exige. O ganho prático é uma trilha
completa: toda decisão humana — aplicada ou recusada — deixa autor, papel, timestamp e
motivo, e o operador para de ver na fila um item que já foi avaliado. O desafio central
não é "gravar um texto", e sim **decidir sem escrever**: rejeitar precisa reusar o mesmo
vocabulário de erros da aprovação (404 cross-tenant, 409 terminal), acrescentar a única
validação que lhe é própria (justificativa obrigatória, 422) e provar que nada toca o
catálogo — preservando o AD-002, pelo qual nenhuma escrita passa pelo caminho do LLM.

## 2. Decisões de Arquitetura

**1. `rejeitar` é o espelho transacional de `aprovar` sem a etapa de escrita: a mesma
ordem 404 → 409 → (422), com um único `commit` ao final.**

O método abre idêntico ao `aprovar`: `CorrectionRepository.get(self.empresa_id,
item_id)`, cujo `empresa_id` vem da sessão autenticada e nunca do corpo da requisição,
de modo que um item de outro cliente simplesmente não existe para esta leitura e vira
`CorrecaoNaoEncontrada` (404, APR-06/ESC-05 sem vazar existência). Em seguida
`_exigir_pendente` recusa itens terminais com `CorrecaoNaoAprovavel` (409), e só então a
justificativa é validada. Manter a **mesma ordem** do `aprovar` é deliberado: a camada
web (T10) mapeia um único conjunto de exceções para os mesmos status, e a resposta nunca
revela algo sobre um item que o tenant não pode ver. O `commit` é único e no fim, na
mesma transação da auditoria — ou a decisão e o evento entram juntos, ou nada entra.

**2. A justificativa é obrigatória e validada por `strip()`, com erro de domínio próprio
(`JustificativaObrigatoria`, 422).**

O design exige que a rejeição registre o *porquê* (APR-03). Para não aceitar um
formulário "vazio" que só tem espaços, `rejeitar` faz `motivo = justificativa.strip()` e
levanta `JustificativaObrigatoria` quando o resultado é vazio; o texto **aparado** é o
que fica em `item.motivo_rejeicao`. O erro entrou em `correcoes/erros.py` ao lado dos
demais, mantendo o serviço ignorante de FastAPI: quem converte a exceção em 422 é a rota
web. É a única pré-condição de rejeição que a aprovação não tinha, e a única que muda o
contrato HTTP do par (404/409 ganham um 422).

**3. Item "sem sugestão" **pode** ser rejeitado: a checagem de sugestão é exclusiva de
`aprovar`.**

Este é o ponto mais sutil do par e o motivo de uma refatoração. `_validar_pendente`
(usada por `aprovar`) fazia duas checagens: estado terminal e ausência de sugestão.
Rejeitar **não** pode herdar a segunda — um item `valor_sugerido is None` não tem o que
aplicar, mas é exatamente o caso que a decisão de design 2 manda recusar conscientemente
("só pode ser rejeitado"). Extraiu-se `_exigir_pendente` (só o estado) e `_validar_pendente`
passou a ser `_exigir_pendente` + checagem de sugestão; `rejeitar` chama só a primeira.
Sem essa separação, um item sem sugestão ficaria preso na fila para sempre — nem
aprovável nem rejeitável —, contradizendo a regra de negócio.

**4. O evento `correcao_rejeitada` carrega apenas metadados operacionais, por um helper
que é fonte única com a aprovação.**

O `detalhe` é montado por `_detalhe_item(item)`, extraído nesta task para eliminar a
duplicação do literal `{item_id, tipo, alvo_chave, campo}` que existia no `rejeitar` e no
`_finalizar` da T7. O design exige que `correcao_aprovada`, `correcao_aplicada` e
`correcao_rejeitada` tenham a **mesma** forma; centralizar o dicionário elimina o risco
de as três formas divergirem em silêncio (L-013 aplicada a chaves de auditoria).
Coerentemente com o ESC-06, o `detalhe` **nunca** carrega `justificativa`/`motivo_rejeicao`
— o texto livre do usuário fica no item, alcançável por `item_id` — nem PII.

**5. A terminalidade é imutável e exercitada por todo o conjunto de estados terminais.**

O guard `_exigir_pendente` cobre `{rejeitado, aplicado, falhou}`, e não só um estado.
O self-review parametrizou `test_rejeitar_item_terminal_recusa` nesses três estados,
asseverando que o item permanece inalterado e que `motivo_rejeicao` continua `None` — a
garantia de que uma segunda decisão (EDG-04) não sobrescreve a justificativa de um item
já encerrado. A lição **L-023** fixa a regra: quando o guard cobre um conjunto, o teste
precisa percorrê-lo inteiro, não um representante.

**6. Nenhuma escrita no catálogo e nenhum caminho pelo grafo (AD-002).**

`rejeitar` não chama `_escrever`/`upsert`: sua única mutação é no próprio `ItemCorrecao`
e no `AuditLog`. O serviço continua sem importar `agents/` ou `graph`, e o teste
`test_rejeitar_nao_escreve_no_catalogo` prova o valor do cadastro intacto e a presença
exclusiva de `correcao_rejeitada` na trilha. Assim, a recusa — que é a decisão mais
segura do HITL — permanece incapaz de alterar dado operacional.

## 3. Concessões e Escolhas Práticas (Trade-offs)

- **`motivo_rejeicao` não é truncado nem limitado no serviço.** A coluna é `String(2000)`
  (T1), mas o SQLite não impõe o limite, então uma justificativa muito longa é gravada
  inteira nos testes. O design **não** declara truncamento para esse campo — ao contrário
  do `valor` de auditoria, coberto pela L-020 —, e inventar aqui um teto criaria um
  contrato especulativo. A validação de tamanho pertence à entrada da web (T10), onde há
  contexto de erro de formulário. Fica registrado como limitação para a T10/T12.
- **O papel do aprovador não é validado no serviço.** `rejeitar` recebe `papel` e grava,
  sem checar se é `admin`/`gestor`. A autorização é responsabilidade da rota web (guard
  `exigir_papel`, T10), coerente com a separação domínio/HTTP já usada na aprovação; o
  serviço permanece testável sem TestClient.
- **Ordem 409 antes de 422.** Um item terminal com justificativa vazia responde 409
  (encerrado), não 422. É a ordem do design (passos 1–2 antes do 3) e a mais informativa:
  o estado do item importa mais que o formulário quando a decisão já não é possível.
- **Rejeitar um item "sem sugestão" não gera evento `correcao_falhou`.** Não é falha: é
  uma decisão humana válida, registrada como `correcao_rejeitada`. Distinguir os dois
  eventos evita que a trilha confunda "o sistema não conseguiu" com "a pessoa recusou".
- **Sem *hardening* de concorrência.** Como no `aprovar`, a segunda decisão paralela relê
  o item já terminal e cai no 409 (EDG-04); a janela de corrida real permanece e é a
  decisão 7 do design, a ser endurecida com `UPDATE ... WHERE status='pendente'` quando o
  volume justificar.

## 4. O que vem a seguir (Roadmap Imediato)

- **T9 (Retenção inclui `item_correcao`):** ligará `CorrectionRepository.purgar_expiradas`
  à purga da Empresa, para que itens terminais — inclusive os `rejeitado` produzidos
  aqui — respeitem a política sem tocar o `AuditLog` (AD-022).
- **T10 (Web — fila e decisão):** converterá `CorrecaoNaoEncontrada`,
  `CorrecaoNaoAprovavel`, `CorrecaoAlvoInvalido`, `CorrecaoFalhaEscrita` e
  `JustificativaObrigatoria` em 404/409/422 re-renderizados, com `decisao: DecisaoCorrecao`
  e `justificativa` no formulário (PRG 303), e é onde a validação de tamanho/entrada do
  motivo passa a existir.
- **T11 (Web — trilha):** exporá o histórico P2, onde a justificativa e o autor da
  rejeição ficam auditáveis conforme a decisão de escopo da trilha.
- **T12 (Aceitação):** fechará a rastreabilidade ponta a ponta de aprovar **e** rejeitar
  com dois tenants, incluindo o read-only do chat (AD-002) e o conjunto exato de eventos
  do turno.

## 5. Validação de Qualidade e Segurança

- **Garantias de negócio e isolamento:** a decisão só resolve item pelo `empresa_id` da
  sessão (`test_rejeitar_isola_por_empresa` prova o 404 cross-tenant); a justificativa é
  obrigatória e aparada (`test_rejeitar_exige_justificativa`, parametrizado em `""`,
  `"   "`, `"\n\t"`; `test_rejeitar_grava_estado_e_auditoria` usa `"  valor incorreto  "`
  → `"valor incorreto"`); itens sem sugestão podem ser rejeitados
  (`test_rejeitar_sem_sugestao_permite`); item terminal não é re-decidido em nenhum dos
  três estados (`test_rejeitar_item_terminal_recusa` parametrizado em
  `["rejeitado", "aplicado", "falhou"]`); nada é escrito no catálogo
  (`test_rejeitar_nao_escreve_no_catalogo`). O `detalhe` de `correcao_rejeitada` não
  carrega `justificativa`/`motivo_rejeicao` nem PII.
- **Achados do self-review (corrigidos):** (1) o literal de metadados de auditoria estava
  duplicado entre `rejeitar` e `_finalizar` — extraído `_detalhe_item`, fonte única para
  os eventos; (2) a docstring de `CorrecaoNaoAprovavel` dizia "não permite aprovação",
  mas o erro também serve à rejeição — texto precisado; (3) o teste de terminalidade
  cobria só `aplicado` — parametrizado nos três estados, registrado como **L-023**.
- **Cobertura e testes automatizados:** `tests/correcoes/test_servico_rejeicao.py` (8
  casos, com os parametrizados) cobre validação de justificativa, estado+auditoria, 404,
  isolamento, terminalidade, rejeição sem sugestão, saída da fila e ausência de escrita.
  Gate focado `uv run pytest tests/correcoes --no-cov -q`: **73 passed** (era 71; +2 da
  parametrização). Suíte completa: **363 passed, 99,02%** (gate de 80% ok).
- **Padrões de qualidade:** `uv run black --check src/ tests/` (112 arquivos) e
  `uv run ruff check src/ tests/` verdes; `from __future__ import annotations` presente;
  docstrings em português; sem comentários fora de docstring; `CorrectionService`
  mantém `@dataclass(frozen=True)` espelhando `CopilotService`.
