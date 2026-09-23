# ADR: f2-t07-aprovacao

## 1. Contexto & Objetivo

As tasks anteriores da F2 construíram a fila de correções: os cadastros incompletos do
tenant viram itens pendentes com sugestão determinística (T3/T4/T5) e existe um
vocabulário de auditoria reservado para registrar a decisão humana (T6). O que faltava
era o ato central da história — **a decisão que efetivamente escreve no cadastro**. A T7
entrega exatamente esse ponto: `CorrectionService.aprovar(item_id, user_id, papel)` lê o
item, revalida o alvo contra o mundo atual, aplica o valor pela mesma porta de escrita da
importação (`upsert`), grava a autoria e a auditoria, e tudo isso sem que o caminho do
LLM toque o catálogo. É a operação que transforma uma recomendação em realidade — e por
isso é a operação de maior risco do épico.

O desafio central não é "chamar update", e sim **fechar todas as portas de escrita
indevida**. Quatro tensões governam a task: (a) **não escrever quando não se deve** —
item de outro tenant, item já decidido, item sem sugestão, alvo que sumiu ou que foi
reimportado com outro valor; (b) **não deixar rastro de escrita parcial** — se o
`upsert` falhar, o valor anterior tem de permanecer intacto e o item tem de terminar como
`falhou`, não meio-aplicado; (c) **provar quem mandou aplicar** — decisão, papel,
timestamp e auditoria na mesma transação do sucesso; e (d) **preservar o AD-002** — o
serviço continua fora do grafo, sem nenhum import de `agents/`. O ganho prático é a
promessa de confiança do HITL: nenhuma alteração de cadastro acontece sem que uma pessoa
identificada tenha decidido, e a alteração é reversível em auditoria mesmo quando falha.

## 2. Decisões de Arquitetura

**1. `aprovar` é a unidade de trabalho da decisão: lê pelo escopo da empresa, valida em
ordem, e só então aplica — um `commit` por caminho de saída.**

O método abre com `CorrectionRepository.get(self.empresa_id, item_id)`. O `empresa_id`
vem da sessão autenticada (nunca do corpo da requisição), então um item de outro cliente
simplesmente **não existe** para esta leitura — vira `CorrecaoNaoEncontrada` (404), o que
atende APR-06/ESC-05 sem revelar que o recurso existe alhures. Em seguida `_validar_pendente`
recusa itens em estado terminal (`CorrecaoNaoAprovavel`, 409) e itens sem sugestão
(`valor_sugerido is None`, 409), sem tocar no item: um item encerrado permanece encerrado
(APR-05, EDG-04) e um item "sem sugestão" continua podendo ser rejeitado (decisão de
design 2). A ordem importa: 404 antes de 409, e estado antes de alvo, para que a resposta
nunca revele nada sobre um item que o tenant não pode ver.

**2. O conflito é detectado comparando o valor atual com o snapshot guardado no pedido,
usando a mesma serialização canônica — e nunca sobrescrevendo.**

Depois de resolver o alvo, `aprovar` reimplementa a regra mais sutil do design: lê o
valor corrente com `valor_atual(item.tipo, registro, item.campo)` e compara com
`item.valor_no_pedido` — o snapshot congelado no momento em que a sugestão foi gerada.
Como os dois lados usam o `serializar` compartilhado de `correcoes/completude.py`, a
comparação é estável para texto, inteiro, decimal e vazio. Se divergirem, o registro foi
reimportado entre a geração e a aprovação (EDG-02): o item é encerrado como `falhou` com
`motivo_falha = MOTIVO_CONFLITO` e `CorrecaoAlvoInvalido` (409), **sem** chamar o
`upsert`. O mesmo tratamento vale para o alvo que deixou de existir (EDG-03,
`MOTIVO_ALVO_AUSENTE`): a resolução pelo `alvo_chave` no tenant da sessão usa o método de
busca dos catálogos (`get_by_sku`/`get_by_fornecedor_id`/`get_by_codigo`), que já
normaliza a chave para caixa alta (L-013 da T5), e um retorno `None` encerra o item sem
escrita.

**3. Aplicação e auditoria vivem na mesma transação; a falha de escrita tem caminho
próprio de rollback e re-marcação em transação nova.**

No sucesso, `_decidir` grava `status="aprovado"`, `decidido_por`, `papel_aprovador` e
`decidido_em`; `_escrever` sobrepõe **apenas** o campo corrigido e delega ao `upsert` do
tipo (mesmo caminho da importação, ESC-01); e `_finalizar` fecha `status="aplicado"` +
`aplicado_em`, registra `correcao_aprovada` e `correcao_aplicada` e faz **um `commit`**.
Tudo na mesma transação significa que nunca há uma decisão auditada sem a escrita
correspondente — ou as duas entram, ou nenhuma entra (ESC-02). Quando `_escrever` levanta,
`_falhar_apos_erro` faz `rollback()` e, numa transação nova, relê o item e chama `_falhar`,
que o encerra como `falhou` com `MOTIVO_ERRO_ESCRITA` e registra `correcao_falhou` (ESC-04).
O `rollback` desfaz a mutação in-memory de `_decidir` e qualquer `flush` parcial feito
pelo `upsert`; o valor anterior do cadastro permanece intacto. A escolha de reler o item
após o rollback (em vez de reutilizar a instância expirada) evita escrever sobre um objeto
em estado inválido no identity map.

**4. O no-op é explícito: sugerido igual ao atual encerra como `aplicado` sem sequer
chamar o `upsert` — mas sem perder a auditoria.**

Se `item.valor_sugerido == atual`, `_aplicar` pula `_escrever` e vai direto para
`_finalizar`. Isso implementa EDG-05 ("sem escrita efetiva") sem criar um estado novo nem
um caminho silencioso: o item ainda é decidido (autor, papel, timestamp), sai da fila e
emite `correcao_aprovada` + `correcao_aplicada`. O teste
`test_aprovar_no_op_quando_sugestao_igual_atual` prova a ausência de escrita espionando
`StockRepository.upsert` com `monkeypatch`, o que é a garantia mais direta possível de que
nada foi tocado no catálogo.

**5. O par `tipo → (repositório, chave, método)` e o mapa posicional `_CAMPOS_UPSERT`
concentram o "como escrever" em um único lugar, com trava de paridade e teste por tipo.**

`_FONTES_CADASTRO` passou de 2 para 3 campos por tipo, ganhando o nome do método de busca,
e `_CAMPOS_UPSERT` declara, para cada tipo, a ordem exata dos valores na assinatura do
`upsert` (`estoque → sku, nome, quantidade, minimo, local`, e assim por diante). Manter os
dois mapas no serviço — a camada que já fala com `repositories` — preserva a direção
`apps → agents → libs` e evita que o domínio puro de `completude.py` importe banco. O
risco dessa tabela indexada por tipo é o desalinhamento silencioso de ordem (L-013
aplicada a argumentos posicionais), que gravaria valores trocados sem levantar erro. Por
isso o self-review acrescentou `test_aprovar_aplica_fornecedor` e
`test_aprovar_aplica_transporte`, fechando a lacuna de a suíte exercitar a aplicação apenas
em `estoque`; agora cada tipo do mapa tem seu próprio teste de escrita.

**6. As exceções de domínio carregam o mapeamento HTTP por tipo, e o serviço não conhece
FastAPI.**

`src/gestlog/correcoes/erros.py` introduz a base `ErroCorrecao` e quatro especializações:
`CorrecaoNaoEncontrada` (404), `CorrecaoNaoAprovavel` (409 terminal/sem sugestão),
`CorrecaoAlvoInvalido` (409 alvo ausente/conflito) e `CorrecaoFalhaEscrita` (falha de
escrita). O serviço levanta o erro de domínio; quem o converte em status HTTP é a camada
web (T10). Mesmo `CorrecaoNaoAprovavel` e `CorrecaoAlvoInvalido` expondo `motivo`, o
detalhamento não vaza para a resposta HTTP além do que T10 decidir — a fronteira
`apps → agents → libs` permanece, e a suíte de domínio testa o serviço sem TestClient.

**7. O `detalhe` de auditoria é pobre de propósito: só metadados de catálogo, com o valor
truncado e nunca texto livre do usuário.**

Os eventos carregam `{item_id, tipo, alvo_chave, campo}`, e `correcao_aplicada` acrescenta
`valor` — dado operacional de catálogo, não o que o usuário digitou. `justificativa` e
`motivo_rejeicao` nunca entram no `detalhe` (ESC-06); o `motivo` de `correcao_falhou` é um
**código** de falha (`registro alvo inexistente`, `registro alterado após a sugestão`,
`erro ao aplicar a correção`), não texto livre. O self-review fechou o contrato do
"valor truncado" prometido no design e na ADR da T6: `_valor_auditavel` corta o valor em
`_LIMITE_VALOR_AUDITORIA = 255` antes de montá-lo no `detalhe`, sem confiar no `String(255)`
da coluna (que o SQLite não impõe). O valor completo continua no item, alcançável por
`item_id`.

## 3. Concessões e Escolhas Práticas (Trade-offs)

- **`except Exception` cerca `_escrever` inteiro.** O design determina que "qualquer
  exceção na aplicação" faça rollback e marque `falhou` (ESC-04), então o serviço trata
  amplamente e converte em `CorrecaoFalhaEscrita`. O custo é que um erro de programação
  (um `KeyError` em `_CAMPOS_UPSERT`, por exemplo) seria reetiquetado como falha de
  aplicação em vez de estourar como bug. Aceitável porque a consequência é *fail-safe* — o
  item termina terminal e o valor anterior fica intacto — e porque um erro de programação
  ainda aparece no log e no teste que o exercita. Restringir o `except` a
  `SQLAlchemyError` deixaria erros de conversão de valor escaparem como exceção genérica
  sem encerrar o item, pior para a trilha.
- **Concorrência resolvida por releitura, não por `UPDATE ... WHERE status='pendente'`.**
  A segunda decisão paralela relê o item já terminal e cai no 409 (EDG-04), o que cobre o
  caso comum. A janela de corrida real (duas leituras antes do commit) permanece e é a
  decisão 7 do design: o *hardening* com `UPDATE ... WHERE status='pendente'` + rowcount
  fica para quando o volume justificar, pois em F2 o item é decidido por uma requisição
  autenticada e o custo de um estado duplicado é uma fila, não uma escrita divergente.
- **`_resolver_alvo` trata tipo desconhecido como 409 (`CorrecaoNaoAprovavel`), não como
  erro interno.** Um `tipo` que não está em `_FONTES_CADASTRO` só surge de dado corrompido
  na fila; classificar como "não aprovável" mantém a resposta dentro do contrato HTTP da
  rota, sem transformar um item defeituoso em 500. É uma escolha defensiva, não uma
  validação de entrada.
- **Status do item continuam literais (`"pendente"`, `"aprovado"`, `"aplicado"`,
  `"falhou"`) espalhados no serviço.** Não há enum central de estados em F2 (o design usa
  strings), e introduzir um só para a T7 seria refatoração de escopo maior que a task. O
  custo é uma divergência silenciosa possível se um estado for renomeado no futuro; a
  mitigação é o repositório já ter os recortes nomeados (`_STATUS_TERMINAIS`/`_STATUS_ABERTOS`)
  e os testes fixarem as transições.
- **O valor auditado truncado perde o sufixo.** Em troca de um `detalhe` sempre curto e
  previsível (ESC-06), a auditoria não guarda o valor inteiro quando ele excede 255
  caracteres. O design aceita esse recorte porque o valor íntegro permanece no item; a
  alternativa — confiar só no comprimento da coluna — falharia silenciosamente no SQLite,
  que não impõe `VARCHAR`.

## 4. O que vem a seguir (Roadmap Imediato)

- **T8 (Rejeição com justificativa):** consumirá o mesmo vocabulário de 404/409 e emitirá
  `correcao_rejeitada`; nasce direto ao lado de `aprovar`, reaproveitando a leitura escopada
  e a ordem de validação.
- **T9 (Retenção):** ligará `CorrectionRepository.purgar_expiradas` à purga da Empresa, para
  que itens terminais (inclusive os `falhou` produzidos por esta task) respeitem a política
  sem tocar o `AuditLog`.
- **T10/T11 (Web):** converterão `CorrecaoNaoEncontrada`/`CorrecaoNaoAprovavel`/
  `CorrecaoAlvoInvalido`/`CorrecaoFalhaEscrita` em 404/409 re-renderizados e exporão a fila
  e a trilha; é onde a decisão humana passa a ter interface.
- **T12 (Aceitação):** fechará a rastreabilidade ponta a ponta com dois tenants, incluindo o
  read-only do chat (AD-002) e o conjunto exato de eventos do turno.

## 5. Validação de Qualidade e Segurança

- **Garantias de Negócio/Privacidade:** a escrita só resolve alvo pelo `empresa_id` da
  sessão (404 cross-tenant em `test_aprovar_isola_por_empresa`); nenhum item terminal ou sem
  sugestão é re-decidido (`test_aprovar_item_terminal_recusa`,
  `test_aprovar_sem_sugestao_recusa`); conflito e alvo ausente encerram sem sobrescrever
  (`test_aprovar_conflito_marca_falhou_sem_sobrescrever`,
  `test_aprovar_alvo_ausente_marca_falhou`); no-op não escreve
  (`test_aprovar_no_op_quando_sugestao_igual_atual`); falha de escrita preserva o valor
  anterior (`test_aprovar_erro_de_escrita_marca_falhou`). O `detalhe` não carrega
  `justificativa`/`motivo_rejeicao` nem PII, e o `valor` é truncado
  (`test_valor_de_auditoria_e_truncado`). A fronteira AD-002 é estrutural: `servico.py` não
  importa `agents/` nem `graph`.
- **Achados do self-review (corrigidos):**
  1. O `detalhe` de `correcao_aplicada` gravava `valor_sugerido` inteiro, contrariando o
     contrato "valor truncado" do design/T6 — corrigido com `_valor_auditavel`
     (`_LIMITE_VALOR_AUDITORIA = 255`), registrado como **L-020**.
  2. A aplicação só era exercitada em `estoque`, deixando o mapeamento posicional de
     `_CAMPOS_UPSERT` de `fornecedores`/`transporte` sem cobertura — corrigido com um teste
     de aplicação por tipo, registrado como **L-021**.
- **Cobertura e Testes Automatizados:** `tests/correcoes/test_servico_decisao.py` cobre os
  três tipos de catálogo, as três pré-condições (404/409 terminal/409 sem sugestão), o
  conflito, o no-op, a falha de escrita com rollback e a trilha de auditoria sem PII. Gate
  focado `uv run pytest tests/correcoes --no-cov -q`: **61 passed** (era 58; +3 do
  self-review). Suíte completa: **351 passed, 99,02%** (gate de 80% ok).
- **Padrões de Qualidade:** `uv run black --check src/ tests/` e `uv run ruff check src/ tests/`
  verdes; `from __future__ import annotations` em todos os módulos; docstrings em português;
  sem comentários fora de docstring; `CorrectionService` mantém `@dataclass(frozen=True)`
  espelhando `CopilotService`, e todos os helpers da T7 ficam bem abaixo dos limites de
  função/arquivo do `AGENTS.md`.
