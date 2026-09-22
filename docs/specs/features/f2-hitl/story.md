# F2 — HITL: escrita com aprovação — Story

**Path:** docs/specs/features/f2-hitl/story.md
**TLC scope:** complex
**Based on:** ROADMAP M2 (Cadastros incompletos + Fluxo de aprovação) e AD-002 (escrita só na F2, via HITL)
**Status:** Rascunho — aguardando aprovação humana (Awaiting human approval)

---

## Problem Statement

Na F1 o copiloto é read-only: recomenda e explica, mas não corrige nada. PMEs
importam cadastros incompletos (campos em branco ou no valor padrão) e o operador
precisa completá-los manualmente, sem apoio e sem trilha de quem mudou o quê. A F2
deixa o copiloto **corrigir/completar cadastros** — sempre com uma decisão humana
explícita antes de qualquer escrita (AD-002) — e registra a autoria de cada escrita.

## Goals

- [ ] O usuário enxerga os registros com campos faltantes do próprio tenant.
- [ ] Para cada campo faltante há uma sugestão de preenchimento explicada (ou a
      marcação explícita de "sem sugestão"), nunca um valor inventado.
- [ ] Toda escrita passa por aprovação humana registrada (quem aprovou, quando e
      com qual justificativa) — nenhuma escrita automática.
- [ ] Cada escrita aplicada gera trilha de auditoria por tenant.
- [ ] O isolamento por tenant é mantido em leitura, decisão e escrita.

## Out of Scope

| Item | Motivo |
| --- | --- |
| Escrita disparada pelo próprio LLM, sem aprovação | Viola AD-002 (HITL é obrigatório) |
| Demais tools de ação do inventário AD-010 (estoque, transporte, fornecedores) | F2 cobre o caminho de correção de cadastros; as demais ações ficam para incrementos seguintes |
| Envio externo de enviar_resposta_logistica | Depende da decisão da questão aberta 4 |
| Correção/completude de documentos | Escopo, formato e regras ainda não definidos |
| Integrações de API em tempo real (TMS/ERP/WMS) | F3 |
| Alertas proativos / automação em background | F4 |
| Relatórios/gráficos e demais dashboards | Fora do épico HITL |
| Detecção em massa sem revisão individual | A decisão humana por item é o núcleo da história |

---

## User Stories

### P1: Listar cadastros incompletos por tenant

**User Story**: Como gestor de logística, quero ver, por tipo de cadastro, quais
registros do meu tenant têm campos faltantes, para saber o que precisa ser corrigido.

**Why P1**: é a porta de entrada — sem visibilidade não existe fila de correção.

**Acceptance Criteria**:
1. WHEN o usuário abre a visão de cadastros incompletos THEN o sistema SHALL listar
   apenas os registros do tenant da sessão que atendem à definição de "incompleto"
   (definição em aberto — ver Open Questions), agrupados por tipo de cadastro.
2. WHEN a lista é exibida THEN o sistema SHALL indicar, por registro, quais campos
   estão faltantes.
3. WHEN um registro de outro tenant é solicitado THEN o sistema SHALL negar
   (404/403) sem vazar a existência do recurso.
4. WHEN não há registros incompletos no tenant THEN o sistema SHALL exibir um
   estado vazio claro.
5. WHEN a requisição não tem sessão válida THEN o sistema SHALL redirecionar ao
   login / responder 401.

**Independent Test**: criar 2 tenants, um com registro incompleto; confirmar que a
lista mostra apenas o registro do tenant correto e os campos faltantes.

---

### P1: Sugerir valores de preenchimento

**User Story**: Como operador logístico, quero receber uma sugestão explicada para
cada campo faltante, para corrigir o cadastro sem montar o valor do zero.

**Why P1**: a sugestão é o conteúdo da correção; sem ela não há o que aprovar.

**Acceptance Criteria**:
1. WHEN um registro incompleto é analisado THEN o sistema SHALL gerar, para cada
   campo faltante, um valor sugerido com base nos dados do próprio tenant.
2. WHEN há sugestão THEN o sistema SHALL apresentar o valor sugerido, uma
   justificativa e a fonte/dado que a sustenta.
3. WHEN não há base suficiente para sugerir THEN o sistema SHALL marcar o campo
   como "sem sugestão", em vez de inventar um valor.
4. WHEN a sugestão é gerada THEN o sistema SHALL mantê-la associada ao registro e
   ao campo correspondente, de forma rastreável até a decisão.
5. WHEN a sugestão é apresentada THEN o sistema SHALL distinguir valor atual, valor
   sugerido e origem da sugestão.

**Independent Test**: dado um registro com campo faltante e dados do tenant que
permitam inferir o valor, ver a sugestão com justificativa; num caso sem base, ver
"sem sugestão".

---

### P1: Aprovar ou rejeitar com justificativa (fila HITL)

**User Story**: Como aprovador autorizado, quero aprovar ou rejeitar cada sugestão
com justificativa, para que nenhuma escrita aconteça sem uma decisão humana.

**Why P1**: é o núcleo do HITL (AD-002) — o gate que separa recomendação de escrita.

**Acceptance Criteria**:
1. WHEN uma sugestão é criada THEN o sistema SHALL apresentá-la como item pendente
   em uma fila de ações acionáveis do tenant.
2. WHEN o aprovador autorizado aprova um item THEN o sistema SHALL registrar a
   decisão de aprovação com usuário, papel e timestamp.
3. WHEN o aprovador autorizado rejeita um item THEN o sistema SHALL exigir
   justificativa e registrar a decisão com usuário, papel e timestamp.
4. WHEN um usuário sem papel autorizado tenta aprovar ou rejeitar THEN o sistema
   SHALL negar (403) sem alterar o item. (Quem é autorizado está em aberto — ver
   Open Questions.)
5. WHEN um item já decidido recebe nova decisão THEN o sistema SHALL recusá-la,
   tratando o item como terminal (idempotência em aberto — ver Open Questions).
6. WHEN um item de outro tenant é acessado THEN o sistema SHALL negar sem vazar a
   existência do recurso.

**Independent Test**: aprovar um item e rejeitar outro com justificativa; ver as
decisões registradas com autor e timestamp; tentar decidir novamente e tentar
decidir sem o papel autorizado.

---

### P1: Aplicar a correção aprovada e registrar a autoria

**User Story**: Como admin da conta, quero que a correção aprovada seja aplicada ao
cadastro e que fique registrado quem aprovou, para confiar que a mudança foi
deliberada e rastreável.

**Why P1**: aprovar sem aplicar não entrega valor; a autoria é a âncora de confiança
(FR-15/SEC-02).

**Acceptance Criteria**:
1. WHEN um item é aprovado THEN o sistema SHALL aplicar o valor aprovado ao
   registro alvo, restrito ao tenant da sessão.
2. WHEN a escrita é aplicada THEN o sistema SHALL registrar auditoria por tenant
   com: ação de escrita, registro e campo afetados, valor aplicado, usuário
   aprovador e timestamp.
3. WHEN a aplicação conclui THEN o item SHALL deixar de aparecer como pendente na
   fila.
4. WHEN a aplicação falha THEN o sistema SHALL preservar o valor anterior do
   registro e sinalizar a falha, sem escrita parcial.
5. WHEN o alvo da escrita pertence a outro tenant THEN o sistema SHALL recusar a
   aplicação sem vazar a existência do recurso.
6. WHEN a auditoria de uma escrita é registrada THEN o detalhe SHALL conter apenas
   os metadados necessários, sem PII desnecessária.

**Independent Test**: aprovar um item, confirmar o registro atualizado e a entrada
de auditoria com autor e timestamp; simular uma falha de aplicação e confirmar que
o valor anterior permanece intacto.

---

### P2: Consultar a trilha de ações

**User Story**: Como gestor de logística, quero consultar o histórico de correções
aplicadas, para auditar quem mudou o quê e quando.

**Why P2**: agrega valor de conformidade, mas depende das histórias P1.

**Acceptance Criteria**:
1. WHEN o gestor consulta o histórico de escritas THEN o sistema SHALL listar as
   ações do tenant com registro, campo, valor, autor e timestamp.
2. WHEN o gestor filtra por período THEN o sistema SHALL respeitar o filtro,
   sempre dentro do tenant.
3. WHEN não há ações no período THEN o sistema SHALL exibir estado vazio.

**Independent Test**: aplicar duas correções e vê-las na trilha, filtrando por
período e confirmando o isolamento por tenant.

---

## Edge Cases

- WHEN o campo tem valor padrão (texto vazio/zero) mas foi importado assim THEN o
  sistema SHALL tratá-lo conforme a definição de "incompleto" a decidir (questão
  aberta 2), sem confundir "vazio" com valor real.
- WHEN um registro tem múltiplos campos faltantes THEN cada campo SHALL ter sua
  própria sugestão e decisão.
- WHEN o registro alvo é alterado ou reimportado entre a geração da sugestão e a
  aprovação THEN o sistema SHALL detectar o conflito em vez de sobrescrever às cegas.
- WHEN o registro alvo deixa de existir antes da aprovação THEN o item SHALL ser
  encerrado sem escrita e com aviso.
- WHEN dois aprovadores decidem o mesmo item em paralelo THEN apenas uma decisão
  SHALL prevalecer; a outra SHALL ser recusada.
- WHEN a sugestão é igual ao valor atual THEN o item SHALL ser tratado sem escrita
  efetiva.
- WHEN o tenant não tem dados importados THEN a visão de incompletos SHALL orientar
  a importar antes.
- WHEN a fila está vazia THEN o sistema SHALL exibir estado vazio claro.
- WHEN o volume de registros incompletos é grande THEN a listagem SHALL permanecer
  utilizável sem travar a interface.
- WHEN a sessão expira durante a decisão THEN o sistema SHALL redirecionar ao login
  sem aplicar a escrita.
- WHEN itens decididos/pendentes alcançam o prazo de retenção THEN o sistema SHALL
  aplicar a política de retenção a decidir (questão aberta 6).

---

## Open Questions

1. **Quem aprova escritas** — admin apenas, admin + gestor, ou qualquer operador? —
   matters because: define as guardas de autorização e o fluxo de aprovação.
2. **O que define "incompleto"**, dado que os campos de catálogo hoje são NOT NULL
   com defaults (texto vazio/zero são indistinguíveis de valor real): tratar
   vazio/zero como ausente ou introduzir colunas anuláveis? — matters because:
   muda o dado persistido, a validação de entrada e a migração.
3. **A sugestão carrega um payload acionável** (ação + registro alvo + argumentos)
   ou é texto livre? — matters because: define se a aprovação pode aplicar a
   correção automaticamente ou apenas orientar o humano.
4. **Escopo de "escritas" na F2** — só correção interna de cadastros ou também o
   envio externo de enviar_resposta_logistica? — matters because: o envio externo
   é irreversível e muda requisitos de confirmação e registro.
5. **Idempotência** — um item aprovado é final/imutável? Reaprovar cria um novo
   item? — matters because: define o estado terminal da fila e como uma nova
   correção do mesmo campo é tratada.
6. **Retenção** — itens de aprovação e trilha seguem a retenção da Empresa ou são
   permanentes para auditoria? — matters because: impacta a política de purga e a
   conformidade.
7. **Onde a fila aparece** — só na interface web/API, ou o copiloto também deve
   surfaçar itens acionáveis no chat? — matters because: a F1 tornou o copiloto
   read-only e o chat sem ações; expor ações no chat muda a fronteira de segurança.

---

**Esta história exige aprovação humana antes de iniciar spec/design/tasks.**
