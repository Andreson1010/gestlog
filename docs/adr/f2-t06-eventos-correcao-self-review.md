# ADR: f2-t06-eventos-correcao

## 1. Contexto & Objetivo

A F2 introduz um caminho de escrita humana — aprovar/rejeitar correções de cadastro —
que até aqui não existia: a aplicação é o primeiro ponto do produto onde uma decisão de
pessoa altera dados. Isso traz uma exigência que o chat não tinha: **provar quem decidiu
o quê, quando e com qual resultado** (ESC-02). A T6 é a fundação dessa prova. Ela não
escreve a decisão (isso é T7/T8), mas define o **vocabulário de eventos** que essas
decisões vão emitir, para que o serviço de aprovação nasça com o catálogo pronto e sem
inventar strings soltas no meio da lógica de negócio.

O objetivo é estender `src/gestlog/audit/eventos.py` com quatro eventos —
`EVENTO_CORRECAO_APROVADA`, `EVENTO_CORRECAO_REJEITADA`, `EVENTO_CORRECAO_APLICADA` e
`EVENTO_CORRECAO_FALHOU` — adicioná-los a `EVENTOS` e documentar, no próprio módulo,
qual *call site* emite cada um e qual o formato do seu `detalhe`. O ganho prático é que
o time de operações ganha, de graça, uma trilha de auditoria das correções: cada decisão
humana deixa registro, e esse registro nunca carrega o texto livre que o usuário digitou
(ESC-06). O desafio central não é adicionar constantes, e sim **fechar o contrato do
`detalhe` antes que existam os consumidores**, sem tocar no conjunto exato de eventos do
turno de chat — que a política de privacidade (AD-022) exige que permaneça imutável.

## 2. Decisões de Arquitetura

**1. `EVENTOS` continua a única fonte de validação, e os quatro valores são idênticos ao
design — nenhum literal novo solto no código.**

As quatro constantes são declaradas junto das já existentes e **adicionadas à tupla
`EVENTOS`**, que já era, desde a F1, o portão de entrada de `registrar_evento` (um evento
fora dela levanta `ValueError`). Manter essa centralização é o que impede que a T7/T8
grave um evento "quase certo" (`correcao_aprovado`, por exemplo) que nenhum relatório
reconheceria. Os valores são exatamente os da tabela do design (`correcao_aprovada`,
`correcao_rejeitada`, `correcao_aplicada`, `correcao_falhou`), o que garante que a trilha
de auditoria futura e os testes de aceitação falem a mesma língua. As constantes também
são reexportadas por `gestlog.audit` (`__init__.py`), seguindo o padrão dos eventos de
chat, para que os consumidores importem da fronteira do pacote e não de um submódulo.

**2. O docstring do módulo é o contrato: cada evento declara explicitamente seu call site
e o *schema* do seu `detalhe`, antes de o código que o emite existir.**

Como a T6 precede os consumidores, o risco real seria a T7 "descobrir" um formato de
`detalhe` diferente do planejado. Para eliminar isso, o docstring do módulo transcreve a
tabela do design: `aprovar` emite `correcao_aprovada` (após validar) com
`{item_id, tipo, alvo_chave, campo}` e, depois do `upsert`, `correcao_aplicada` com
`{..., valor}`; `rejeitar` emite `correcao_rejeitada` com os mesmos metadados; e as
falhas de `aprovar` emitem `correcao_falhou` com `{item_id, motivo}`. Essa escolha torna
o módulo autoexplicativo para quem implementará T7/T8 e fixa o contrato que os testes
de integração dessas tasks devem afirmar.

**3. O `detalhe` é deliberadamente "pobre": só metadados, nunca o texto livre do usuário
nem PII — o conteúdo sensível vive no item, alcançável por `item_id`.**

O núcleo do ESC-06 (`justificativa`/`motivo_rejeicao` podem conter dado sensível) é
resolvido por omissão: o `detalhe` **nunca** carrega esses campos. Ele carrega a
identidade operacional da correção (`item_id`, `tipo`, `alvo_chave`, `campo`), o `valor`
aplicado **truncado** (dado de catálogo, não do usuário) e, na falha, um `motivo` que é
**código de falha** (conflito/alvo/erro), não texto livre. O valor completo permanece no
`ItemCorrecao`, referenciável por `item_id`. Assim, a auditoria é útil para investigar
sem ser um segundo repositório de dados pessoais — e a política de retenção da AD-022
(mantém `AuditLog`, purga o item) permanece coerente: quando o item expira, o registro
de auditoria sobrevive como metadado anonimizado.

**4. Os eventos vivem no caminho de aplicação, nunca no turno de chat — e a T6 não toca
em nenhum call site existente (AD-022).**

A tentação de registrar os eventos de correção "junto do fluxo de auditoria" seria um
erro: `copilot/service.py` registra exatamente `pergunta` e `recomendacao` por turno, e o
teste `test_answer_registra_auditoria_sem_pii` afirma esse **conjunto exato**. Adicionar
um evento novo ao catálogo **não** altera o que o chat emite, porque a validação é por
pertinência e não por exaustão; a T6 apenas amplia o vocabulário permitido. A prova disso
é que a suíte completa permanece verde sem sequer editar o teste do turno — a fronteira
AD-022 está garantida por construção, não por ajuste de asserção.

## 3. Trade-offs e Compromissos

- **O docstring referencia `aprovar`/`rejeitar`, que só existem na T7/T8.** É uma
  referência prospectiva: documentamos o contrato antes do código. Aceitável porque o
  design já nomeia os métodos e a T6 é um tijolo do mesmo épico; o custo é que, se a
  assinatura mudar na T7, o texto precisa acompanhar. A alternativa — só documentar
  depois — adiaria a proteção contratual justamente para a fase em que ela mais serve.
- **`registrar_evento` continua aceitando `detalhe: dict` livre.** Não há *schema*
  executável por evento; o ESC-06 é um contrato de quem chama. Optou-se por não
  introduzir validação de forma no catálogo (over-engineering para F2) — a prova de que
  nenhum call site vaza texto livre virá dos testes de integração da T7/T8.
- **Os dois testes cobrem pertinência e registro, não o *schema* de cada evento.** O
  teste de registro usa um `detalhe` genérico para os quatro eventos; ele prova que o
  catálogo os aceita e os persiste sem commit, que é o *Done when* da T6. Afirmar o
  formato por evento aqui seria duplicar a garantia que a T7/T8 darão no ponto real de
  emissão. Fica registrado que a T6 não "trava" o formato — ela o documenta.
- **Ordenação das constantes segue a tabela do design, não a alfabética.** Em
  `eventos.py` os quatro eventos estão na ordem do design (aprovada, rejeitada,
  aplicada, falhou), enquanto `EVENTOS` e os reexports seguem o agrupamento existente e a
  ordenação exigida pelo isort. Não há impacto funcional (a pertinência é por conjunto),
  apenas legibilidade intencional ligada ao documento de origem.

## 4. Limitações Conhecidas

- **Não há *enforcement* de runtime do `detalhe`.** Um futuro call site que passe
  `justificativa` no `detalhe` não será barrado por `registrar_evento`; a garantia do
  ESC-06 é de disciplina de código e de teste, não de biblioteca.
- **O vocabulário de `motivo` (FALHOU) ainda não está fechado.** A T6 declara que existe
  um `motivo`, mas os códigos concretos (conflito de reimportação, alvo ausente, erro de
  escrita) serão definidos na T7, junto com os ramos que os produzem.
- **O truncamento de `valor` é documentado, mas implementado no call site.** A T6 define
  o contrato; quem efetivamente trunca é a T7, ao montar o `detalhe` de
  `correcao_aplicada`. Até lá, o limite de tamanho é uma promessa textual.
- **A rastreabilidade ponta a ponta dos quatro eventos só fecha nas tasks seguintes.** A
  T6 prova que o catálogo existe e aceita os eventos; a prova de que cada decisão os
  emite nos momentos corretos (após validar, após o `upsert`, no rollback) pertence à T7,
  T8 e à aceitação da T12.

## 5. Validação de Qualidade e Segurança

- **Garantias de negócio/privacy:** os quatro eventos não transportam
  `justificativa`/`motivo_rejeicao` nem PII; o `valor` é dado operacional truncado e o
  conteúdo completo permanece no `ItemCorrecao`, referenciável por `item_id` (ESC-02,
  ESC-06). A fronteira AD-022 foi preservada: `copilot/service.py` não foi tocado e
  `test_answer_registra_auditoria_sem_pii` continua afirmando o conjunto exato
  `{"pergunta", "recomendacao"}` do turno de chat.
- **Achado do self-review:** o docstring do módulo havia resumido o contrato do design e
  omitido o qualificador de que o `valor` é **truncado**, além de deixar ambíguo que o
  `motivo` de `EVENTO_CORRECAO_FALHOU` é **código de falha** e não o texto livre
  `motivo_rejeicao`. Corrigido no próprio docstring; registrado como **L-019**.
- **Cobertura e testes automatizados:** `tests/audit/test_auditoria.py` ganhou
  `test_eventos_de_correcao_estao_no_catalogo` (pertinência a `EVENTOS`) e
  `test_registrar_eventos_de_correcao_sem_commit` (os quatro são aceitos e persistidos na
  mesma transação, sem `commit`). Gate focado `uv run pytest tests/audit --no-cov -q`:
  **11 passed**. Suíte completa: **338 passed, 98,50%** (gate de 80% ok).
- **Padrões de qualidade:** `uv run black --check src/gestlog/audit tests/audit` e
  `uv run ruff check src/gestlog/audit tests/audit` verdes; `from __future__ import
  annotations` presente; docstrings em português; sem comentários fora de docstring;
  reexports ordenados e consistentes com o restante do pacote `audit`.
