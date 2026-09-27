# ADR: f2-t09-retencao

## 1. Contexto & Objetivo

A F2 introduziu uma tabela nova — `item_correcao` — com ciclo de vida próprio: itens
pendentes (trabalho em curso), aprovados, e terminais (`rejeitado`, `aplicado`,
`falhou`). A política de retenção do produto já existia desde a F1: cada `Empresa`
define um prazo (`Empresa.retention_days`) ou usa o padrão do sistema, e
`audit.retencao.purgar_expiradas` percorre as empresas apagando o que venceu. Só que essa
varredura conhecia apenas **conversas**: a tabela de correções, criada depois, ficou fora
do laço. O efeito prático era silencioso e indesejado — itens de correção decididos há
anos continuariam ocupando a fila e o banco indefinidamente, ignorando a política que o
tenant configurou (EDG-10).

A T9 liga as duas pontas em `src/gestlog/audit/retencao.py`: a mesma passada por empresa
que purga conversas passa a purgar também os itens de correção decididos além do prazo,
somando as duas contagens. O ganho de negócio é a coerência da promessa de retenção —
"o que eu configurei vale para os meus dados" — sem abrir mão da regra de conformidade
que sempre acompanhou essa promessa: o `AuditLog` **não** é purgado (AD-022). O desafio
central é, portanto, de composição: acrescentar uma segunda fonte de dados a uma
varredura multitenant, sem duplicar a lógica de prazo, sem tocar a trilha canônica e sem
purcar trabalho operacional ainda em curso.

## 2. Decisões de Arquitetura

**1. Uma única passada por empresa reaproveita o mesmo `limite` para as duas fontes, e
`retencao_dias` segue sendo a única definição de prazo.**

O laço de `purgar_expiradas` calcula `limite = momento - timedelta(days=retencao_dias(
empresa, settings))` e o entrega tanto ao `ConversationRepository` quanto ao
`CorrectionRepository`. Nada de um segundo cálculo de prazo para correções: a política
por tenant é uma só, e as duas tabelas operacionais a respeitam idêntica. Essa escolha é
a aplicação direta da L-013 (fonte única de verdade): se cada tabela tivesse seu próprio
prazo, uma mudança de política corrigiria uma e esqueceria a outra. O isolamento por
`empresa.id` também vem do mesmo laço — cada tabela purga apenas a sua empresa.

**2. A correção entra como mais uma parcela do total, preservando o contrato `-> int`.**

O retorno passou a ser "total de registros removidos (conversas + itens)". Manter o tipo
`int` e apenas somar `correcoes.purgar_expiradas(...)` preserva todos os chamadores e a
semântica de "quantos registros a retenção apagou". Os repositórios já devolvem `0`
quando não há o que remover, então empresas sem itens ou sem nada vencido não quebram o
laço — o caminho vazio é exercitado pelos testes de conversa que já existiam.

**3. A purga de correções é delegada ao `CorrectionRepository` (T2), que já concentra a
regra: *allow-list* de estados terminais e corte por `created_at`.**

`CorrectionRepository.purgar_expiradas` seleciona ids com
`status.in_(("rejeitado", "aplicado", "falhou"))` e `created_at < limite`, nunca
`pendente`/`aprovado`. A T9 **compõe** esse método em vez de escrever SQL novo na camada
de retenção — a porta de acesso ao banco continua sendo `libs`, e a definição de "item
decidido" continua num só lugar. O corte é por `created_at` (e não `decidido_em`),
conforme o design e o padrão do `ConversationRepository`: a política é sobre a **idade do
registro**, não a idade da decisão. O self-review precisou nomear a coluna no docstring
desse método — a presença de dois timestamps (`created_at`/`decidido_em`) tornava o texto
anterior ("anteriores a `limite`") ambíguo, exatamente o risco da L-019; a correção está
fixada como **L-025**.

**4. Itens pendentes/aprovados permanecem: retenção remove histórico decidido, não
trabalho em curso.**

A distinção entre estados abertos e terminais é o que separa "dado que já cumpriu seu
papel" de "fila operacional". Um item ainda `pendente` é uma decisão que o tenant ainda
deve tomar; apagá-lo por retenção silenciaria uma correção que o gestor nem viu. Por
isso a composição preserva a allow-list da T2 e o teste
`test_purga_remove_itens_de_correcao_decididos` fixa que, entre cinco itens vencidos de
todos os estados, apenas os três terminais somem — os dois abertos ficam.

**5. O `AuditLog` continua não purgado (AD-022), e a T9 prova isso na mesma transação.**

A purga remove o dado operacional (a conversa, o item), mas a trilha de conformidade
sobrevive para que a decisão permaneça investigável. A prova é
`test_purga_preserva_audit_log`: um item vencido é apagado e o evento
`correcao_aplicada` correspondente permanece. Isso mantém coerência com o design da P2 —
o `AuditLog` é a trilha canônica justamente porque não é purgado — e fecha o *rabbit
hole* "item some antes do log" registrado desde a T2, no lado do que permanece.

**6. O isolamento e o prazo por empresa ganharam teste próprio para a nova tabela,
replicando o que já existia para conversas.**

O self-review apontou a lacuna: os novos testes de correção usavam um tenant só, e
`test_purga_isola_entre_empresas` cobria apenas conversas. Uma regressão na composição
por empresa (usar o `limite`/`empresa.id` de outra empresa para os itens) passaria em
silêncio. Foi acrescentado `test_purga_itens_isola_entre_empresas` — empresa com prazo
de 30 dias tem o item vencido removido, empresa com 365 dias o preserva, e o total é
`1`. É a mesma classe de cuidado das lições L-021/L-023 e ficou registrada como **L-024**:
ao estender um laço multitenant para uma tabela nova, replique os testes de
isolamento/prazo-por-empresa que já existem para as tabelas antigas.

## 3. Concessões e Escolhas Práticas (Trade-offs)

- **O total agregado perdeu a especificidade "conversas".** Antes, `purgar_expiradas`
  devolvia o número de conversas removidas; agora devolve conversas **+** itens. Não há
  consumidor que dependa da distinção (a função é usada por job/teste como "quanto foi
  purgado"), e separar as contagens num par (`tuple`/`dict`) mudaria o contrato sem
  necessidade. A docstring passa a dizer "registros removidos" para não induzir a
  leitura antiga.
- **O corte é por `created_at`, não por `decidido_em`.** Um item gerado há muito tempo e
  decidido ontem é purgado assim que a retenção vence — a política declarada é sobre a
  idade do registro, e adotar a idade da decisão para correções criaria uma regra
  diferente da das conversas, sem base no design.
- **Sem `delete` em cascata.** O item de correção não tem dependentes (ao contrário da
  conversa, que arrasta mensagens/recomendações/feedback); a composição reaproveita o
  `select ids → delete in_` simples da T2, sem introduzir um shape paralelo.
- **A purga continua sendo uma varredura completa por empresa, em memória para os ids.**
  É o mesmo perfil da purga de conversas e da geração da fila; para o volume do F2 é
  aceitável, e um `DELETE ... RETURNING`/`rowcount` em massa é a evolução isolada quando
  a tabela justificar, sem mudar o contrato.
- **`purgar_expiradas` continua não sendo chamado por nenhum job agendado nesta task.**
  A T9 liga a política aos itens; o agendamento/execução periódica da purga é operação
  do sistema, fora do escopo de uma task de retenção.

## 4. O que vem a seguir (Roadmap Imediato)

- **T10 (Web — fila e decisão):** exporá a fila materializada e a decisão humana via
  `GET /correcoes` e `POST /correcoes/{id}/decisao` (PRG 303), convertendo as exceções de
  domínio em 404/409/422 re-renderizados.
- **T11 (Web — trilha P2):** servirá o histórico das correções aplicadas com filtro de
  período, onde a interação com a retenção (itens somem, `AuditLog` permanece) fica
  visível ao gestor.
- **T12 (Aceitação):** fechará a rastreabilidade ponta a ponta — listar → sugerir →
  aprovar → aplicar → auditar → trilha e rejeitar — com dois tenants, incluindo o
  read-only do chat (AD-002) e o conjunto exato de eventos do turno.

## 5. Validação de Qualidade e Segurança

- **Garantias de negócio e isolamento:** a purga remove apenas itens terminais vencidos e
  preserva pendentes/abertos (`test_purga_remove_itens_de_correcao_decididos`); o
  isolamento e o prazo por empresa são provados para a nova tabela
  (`test_purga_itens_isola_entre_empresas` — vencida 30d removida, retida 365d
  preservada); o `AuditLog` não é tocado (`test_purga_preserva_audit_log`); o corte por
  `created_at` está explícito no docstring do repositório (L-025).
- **Achados do self-review (corrigidos):** (1) faltava teste de isolamento/prazo por
  empresa para `item_correcao` — acrescentado, registrado como **L-024**; (2) o docstring
  de `CorrectionRepository.purgar_expiradas` não nomeava a coluna do corte (`created_at`
  vs. `decidido_em`) — corrigido, registrado como **L-025**.
- **Cobertura e testes automatizados:** `tests/audit/test_auditoria.py` cobre a purga de
  conversas (inalterada), a purga de itens, o isolamento multitenant e a preservação do
  `AuditLog`. Gate focado `uv run pytest tests/audit --no-cov -q`: **14 passed**. Suíte
  completa: **366 passed, 99,03%** (gate de 80% ok); `src/gestlog/audit/retencao.py` com
  **100%** de cobertura de linha.
- **Padrões de qualidade:** `uv run black --check src/ tests/` (112 arquivos) e
  `uv run ruff check src/ tests/` verdes; `from __future__ import annotations` presente;
  docstrings em português; sem comentários fora de docstring; retenção permanece sem
  conhecer HTTP nem o grafo.
