# ADR: seguranca-sweep T3 — PII/LGPD (redação + retenção)

## 1. Contexto & Objetivo

A T3 fecha o eixo de LGPD do sweep de segurança: até aqui, o texto do usuário
ia ao LLM com e-mail, CPF e CNPJ em claro — dados que a LGPD exige minimizar —
e a rotina de retenção, embora já purgasse conversas e correções por empresa,
deixava dois buracos: o **e-mail** de convites expirados/usados permanecia no
banco para sempre (I-10), e uma linha legada com `retention_days <= 0`
transformaria a rotina em um aspirador de tudo, porque `limite = agora -
timedelta(days=negativo)` empurra o corte para o futuro distante — o oposto do
desejado (I-11). Os requisitos são **PII-01..04** e **EDG-07**, e o critério de
aceite é comportamental: o que o modelo vê, o que o histórico guarda e o que a
auditoria registra contêm apenas marcadores; a empresa congelada não perde
**nada**; as demais seguem purgando normalmente.

O desafio técnico tem três faces: (a) uma ordem de expressões regulares que
resolve a ambiguidade entre padrões que compartilham dígitos pontuados — e que
precisa ser provada, não presumida; (b) uma purga que zera dado pessoal sem
destruir a trilha de auditoria; (c) um fail-safe em duas camadas (aplicação e
banco) que não pode depender do dialeto.

## 2. Decisões de Arquitetura

### 1. Ordem fixa das regexes: EMAIL → CNPJ → CPF → TELEFONE → ENDERECO → CEP → NOME

A ordem não é cosmética — é o mecanismo de desambiguação. E-mail vem primeiro
porque o `@` o torna disjunto de todo o resto: se fosse aplicado depois, um CPF
mascarado já teria virado `[DOCUMENTO]` e não haveria conflito, mas um e-mail
com números no domínio poderia colidir com a cauda de outro padrão; aplicá-lo
primeiro elimina a classe de problema. `CNPJ` vem antes de `CPF` porque os dois
compartilham a forma pontuada e o CNPJ tem 14 dígitos contra 11 do CPF: a regex
de CPF (`\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b`) nunca casa no meio de um run de
dígitos (o `\b` final exige fronteira), mas a ordem explícita CNPJ→CPF remove a
dependência dessa propriedade sutil. Documento antes de telefone é a decisão
com consequência de produto visível: os padrões compartilham dígitos, e a
redação é um pipeline de substituições — o primeiro padrão que casa consome o
trecho. O discriminante `test_cpf_nao_e_capturado_como_telefone` prova a
propriedade por **categoria** (e não por ausência de redação), e o revert
empírico contra a base (`1cee0af`) confirmou que ele fica vermelho sem a
mudança.

Sobre o risco de backtracking catastrófico: todos os padrões novos têm
quantificadores limitados sobre classes de caractere disjuntas
(`\d{2}\.?\d{3}...`, `{2,}` no TLD) — não há quantificador aninhado nem
ambiguidade exponencial; o pior caso do `_EMAIL` sobre um token longo sem `@`
é quadrático com constante mínima, o mesmo perfil dos padrões de telefone que
já existiam.

### 2. A ambiguidade CPF/telefone-11-dígitos é resolvida a favor do documento (DESVIO 2, aceito)

Um telefone sem máscara (`11987654321`) e um CPF sem máscara são a mesma string
de 11 dígitos — nenhuma regex consegue distingui-los sem semântica. A ordem
fixada resolve o empate a favor de `[DOCUMENTO]`: a redação **nunca** se perde
(a string não chega ao LLM de nenhum jeito), só a categoria na auditoria muda.
Telefones com qualquer vestígio de máscara — `(11) 98765-4321`, `11 98765-4321`,
`1198765-4321`, `+55 11 98765-4321` — continuam casando como `[TELEFONE]`,
porque o hífen/parêntese quebra o casamento do CPF. O custo é um falso positivo
de categoria (telefone rotulado como documento) e um falso positivo de
redação em SKU/rastreio puramente numérico de 11 ou 14 dígitos — direção
segura para LGPD (minimização excessiva, nunca insuficiente), e o `\b`
inicial impede que códigos alfanuméricos (`BR12345678901`) sejam tocados. O
caso está documentado no docstring do teste e aqui; a alternativa (ordem
inversa) seria pior: CPF mascarado viraria `[TELEFONE]`, deslocando a categoria
do caso **mais** comum e semanticamente mais sensível.

### 3. Purga de `Convite.email` com assinatura por empresa (DESVIO 1, justificado)

O design esboçou `purgar_emails_de_convites(session, agora)` global; a
implementação assina `(session, empresa_id, agora)`. O desvio é **coerência
interna do próprio design**: a seção do fail-safe (PII-03) exige que a empresa
com prazo inválido não tenha "nada purgado — conversas, correções **nem
convites**". Uma chamada global no fim de `purgar_expiradas` purgaria o convite
da empresa congelada, contradizendo a outra metade do design. A assinatura por
empresa coloca a purga dentro do loop, depois do guard — a empresa congelada
perde exatamente zero registros, e o teste
`test_retention_days_zero_recusa_purga_e_loga_erro` assegura as duas direções
(convite da congelada intacto, convite da normal zerado). O `UPDATE ... WHERE
... email != ""` mantém a linha para auditoria (AD-015), é idempotente por
construção (linha já zerada não é recontada — provado por teste de segunda
passagem) e reusa o `agora` aware com o guard de fuso que a rotina já exigia
(L-031). O total reportado pela rotina passa a incluir convites zerados,
contados na mesma métrica.

### 4. Fail-safe em duas camadas: guard na rotina + constraint no banco

`retention_days <= 0` é recusado em três portas independentes, cada uma
cobrindo um vetor diferente:

- **Repositório** (`EmpresaRepository.create`): `ValueError` antes do flush —
  erro de aplicação legível antes do erro de banco opaco.
- **Constraint** (`ck_empresa_retention_positiva`): qualquer escrita fora do
  repositório (script, seed, migração futura) esbarra no banco. A condição
  `retention_days IS NULL OR retention_days >= 1` preserva o fallback para o
  padrão do sistema, que `Settings` já garante positivo (`gt=0`).
- **Rotina de purga**: `logger.error` com o valor e o `empresa.id` (o teste
  assegura ambos no `caplog`, ancorado no logger explícito
  `gestlog.audit.retencao` — robusto ao fix da T2 de
  `disable_existing_loggers=False`) e `continue` — a recusa é por empresa, não
  aborta o lote (EDG-07: uma empresa com dado ruim não congela a conformidade
  das outras).

Como a constraint impede **persistir** a linha inválida, o estado que o guard
da rotina defende só existe em bancos pré-migração — por isso o teste simula o
prazo legado via monkeypatch de `retencao_dias` (DESVIO 3). O teste é
representativo e válido: a função mockada é a única porta por onde a rotina lê
o prazo, e o cenário que ela reproduz (linha legada com 0) é real e
documentado.

### 5. `batch_alter_table` para a constraint: portabilidade SQLite/Postgres

O SQLite não aceita `ADD CONSTRAINT`; o `batch_alter_table` recria a tabela
nesse dialeto e segue o caminho nativo no Postgres — uma única definição da
migração atende aos dois. O efeito é fail-closed por construção: valor legado
inválido faz a própria migração falhar, forçando a correção antes do deploy em
vez de semear o banco com uma empresa-bomba. O round-trip do teste asserção por
efeito (ausente antes do upgrade, presente depois, recusa 0 com
`IntegrityError`, removido no downgrade com nova semeadura de 0 bem-sucedida),
contra um banco descartável por teste (fixture `alembic_config` cria e derruba
o database no Postgres — nenhum resíduo persistente). A revisão encadeia de
`f2b3c4d5e6f7` (índice case-insensitive da T2), sem colisão de revision id.

## 3. Trade-offs & Compromissos

- **Telefone sem máscara rotulado como `[DOCUMENTO]`** — sacrificamos a
  precisão de categoria no caso ambíguo em troca de uma ordem de regex simples
  e provável de manter. Aceitável porque o objetivo do requisito é
  minimização (atingida em 100%) e a auditoria registra a categoria como
  *aproximação*, não como verdade.
- **Falso positivo em rastreio/SKU numérico** — um código numérico puro de 11
  ou 14 dígitos é redigido como documento. Aceitável pela direção do erro
  (excesso de privacidade) e pela improbabilidade operacional (códigos
  logísticos reais quase sempre têm prefixo alfabético, que o `\b` protege).
- **`UPDATE` direto fora de `repositories/`** — `purgar_emails_de_convites`
  emite a statement SQLAlchemy dentro de `audit/retencao.py`, e não num
  repositório. O design aprovado especifica exatamente essa forma (§T3), e há
  precedente de construtos de consulta em `auth/`; a semântica da purga é
  política de retenção, não CRUD de domínio, o que justifica a co-localização.
  Se o pacote `audit/` crescer statements, vale extrair um repositório de
  convites numa refatoração futura.
- **Cobertura Postgres local** — a matriz de dialetos rodou só SQLite no host
  (daemon docker parado); o Postgres fica para o CI. A migração usa
  `batch_alter_table`, portável por construção, e o teste de round-trip é
  dialético.

## 4. Limitações Conhecidas

- A desambiguação telefone/documento é lexical, não semântica — um run de 11
  dígitos sempre será `[DOCUMENTO]`. Um parser com validação de dígito
  verificador de CPF classificaria melhor, ao custo de acoplar a redação a uma
  regra fiscal.
- O e-mail do convite é zerado, mas `papel`, `token_hash` e datas permanecem —
  intencional (AD-015: trilha de auditoria do convite). O `token_hash` de
  convite expirado já é inaceitável por `_convite_valido`, então a purga não
  cria buraco de segurança.
- Linhas legadas com `retention_days <= 0` travam o deploy da migração
  (fail-closed): o operador precisa corrigir os valores antes de atualizar —
  decisão documentada no spec, não automatizada.
- Convites criados e nunca usados dentro do prazo retêm o e-mail até
  expirarem — conforme o requisito (dado com finalidade ativa).

## 5. Self-review — achados e verificação

Nenhum achado exigiu correção de código. Verificações empíricas desta
revisão:

- **Discriminantes provados vermelhos na base** (L-053, `git restore --source
  1cee0af`): `test_cpf_nao_e_capturado_como_telefone` e
  `test_email_redigido` falham sem o novo `redacao.py`;
  `test_insert_empresa_retention_days_zero_e_recusado` falha sem o
  `CheckConstraint` — working tree restaurada e `git status` limpo depois.
- **Gate final**: 660 passed, 3 skipped, cobertura 99,10% (gate de 80%
  satisfeito); `ruff check` e `black --check` limpos nos três alvos.
- **Higiene**: funções ≤ 50 linhas, arquivos ≤ 800, `from __future__ import
  annotations`, logging sem `print`, sem comentários fora de docstrings,
  português nos textos e inglês nos identificadores — conforme AGENTS.md.
