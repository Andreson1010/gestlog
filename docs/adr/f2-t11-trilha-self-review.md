# ADR: f2-t11-trilha

## 1. Contexto & Objetivo

A T10 entregou a fila de correções e a decisão de aprovar/rejeitar pela interface:
o admin ou gestor via o que estava pendente e agia. O que ainda não existia era a
memória do que já tinha acontecido. Quem revisou uma sugestão não conseguia,
depois, responder à pergunta de conformidade mais elementar — *quem mudou o quê,
quando* — sem abrir o banco. A T11 fecha essa lacuna com `GET /correcoes/historico`:
uma trilha por tenant, filtrável por período, com registro, campo, valor, autor e
timestamp, e um estado vazio claro quando não há nada no intervalo consultado. O
valor de negócio é direto: auditoria de escritas cadastrais deixa de depender de
acesso técnico e passa a caber numa tela para o gestor de logística.

O desafio arquitetural não é desenhar a tabela — a tabela já existe e o
`CorrectionRepository.listar_trilha` (T2) já sabe buscá-la com escopo de empresa.
O trabalho real está em três frentes pequenas e interligadas: resolver o **e-mail
do autor** sem escrever SQL na camada web, traduzir o período de datas do formulário
(`desde`/`ate`) para o intervalo inclusivo que o repositório espera, e provar que a
página **não vaza** entre tenants. Tudo isso reaproveitando ao máximo o que as tasks
anteriores já blindaram.

## 2. Decisões de Arquitetura

**1. Um `UserRepository` dedicado para resolver o e-mail do autor, mantendo o SQL
fora de `web/`**

A trilha guarda `decidido_por` como `UUID`; a tela precisa mostrar algo legível, e
a escolha de negócio foi o **e-mail** do autor, não o id. Isso exigiu uma leitura da
tabela de usuários, e foi aqui que a fronteira do projeto decidiu o desenho: a regra
do repositório é que **nada fora de `db/` + `repositories/` escreve SQL**. Em vez de
colocar um `select` no router, nasceu `UserRepository.emails(ids)`, que recebe uma
`Sequence[UUID]`, deduplica com `set`, devolve um `dict[UUID, str]` e — importante —
exclui silenciosamente ids sem usuário correspondente, para que o template possa cair
num `"—"` em vez de estourar. Há um ganho prático além do organizacional: como o
mapa é construído em **uma única consulta** `WHERE id IN (...)`, a trilha inteira é
renderizada sem o clássico N+1, e autores repetidos são resolvidos uma só vez.
O `__init__` do pacote reexporta `UserRepository`, alinhando-o às demais fábricas de
repositório e mantendo o ponto de descoberta único.

**2. A trilha é consultada direto do repositório, como o dashboard já faz com os KPIs**

A rota chama `CorrectionRepository(session).listar_trilha(empresa_id, desde, ate)` e
não passa por um serviço de domínio. É o mesmo padrão de `web/kpis.py`, que lê
`KpiRepository` diretamente. A justificativa é econômica e de escopo: a trilha é
**leitura pura** — não decide, não escreve, não aplica regra —, então criar um
`CorrectionService.listar_trilha` seria uma camada de passagem sem valor, piorando a
navegação do código. A regra de negócio de *o que entra na trilha* continua no
repositório, que já é a fonte única dessa definição. Depender do contrato de leitura
pronto da T2 também garante que a tela herde de graça a ordenação (mais recentes
primeiro) e o corte temporal por `decidido_em`.

**3. A trilha cobre `aplicado` e `falhou`; `rejeitado` fica deliberadamente de fora**

A pergunta da P2 é "o que foi **aplicado** no cadastro", e é isso que o negócio
chama de trilha de correções. `aplicado` representa uma escrita (ou um no-op
consciente) que mudou o cadastro; `falhou` representa uma tentativa que não escreveu
— mas que o operador precisa ver para entender por que a correção não foi adiante.
`rejeitado`, embora seja um estado terminal e auditável, **não gerou escrita** e
portanto não pertence a esta visão; seu rastro de conformidade continua no
`AuditLog` canônico. Essa separação já está codificada em
`_STATUS_TRILHA = ("aplicado", "falhou")` dentro do `CorrectionRepository`, e a T11
não a reimplementa: apenas a consome. Manter a decisão em um único ponto evita que a
página e a purga de retenção divirjam sobre o que é "trilha".

**4. Filtro inclusivo de período com o padrão de datas de `web/kpis.py`**

O formulário manda `date` puro (`2026-06-01`), enquanto `decidido_em` é um
`datetime`. A conversão vive em `_inicio`/`_fim`: o início vira `time.min` do dia, o
fim vira `time.max`, ambos com `tzinfo=UTC`, e as comparações são inclusivas
(`>=`/`<=`). O efeito prático é que "De 01/06 a 30/06" inclui **todo** o dia 30, e não
só a meia-noite — o erro clássico de excluir o último dia. Repetir o par de
helpers que `kpis.py` já usa mantém a experiência de período idêntica entre dashboard
e histórico: mesmos nomes de parâmetro, mesmo comportamento e o mesmo preenchimento
dos campos do formulário via `desde.isoformat()`. A alternativa de um util comum
foi considerada e adiada (ver trade-offs), para não tocar o dashboard nesta task.

**5. Estado vazio e navegação cruzada fila ↔ histórico**

Quando o filtro não devolve linhas, a página não mostra uma tabela em branco: exibe
um aviso `role="status"` — *"Nenhuma correção aplicada no período"* — com um link de
volta para `/correcoes`. No sentido oposto, o cabeçalho da fila ganhou o link "Ver
histórico". Os dois links transformam as duas telas numa única jornada operacional:
o gestor entende que a fila é o *agora* e o histórico é o *antes*, e não precisa
adivinhar a URL. O estado vazio é honesto quanto ao recorte: ele fala de "no
período", não de "nunca houve", o que é a leitura correta quando o filtro é a causa
da lista vazia.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **Sem paginação/limite na trilha.** `listar_trilha` aceita `limite`, mas a rota não
  passa nenhum: a página carrega todo o histórico do período. Diferente da fila (que
  é operacional e protegida por `_LIMITE_MAXIMO`), a trilha é uma consulta de
  auditoria e truncá-la silenciosamente seria pior do que listá-la. Se o volume
  crescer, a T11 está pronta para receber o mesmo `limite` validado por `Query`.
* **`_inicio`/`_fim` duplicados de `kpis.py`.** São dois helpers idênticos em dois
  routers. Extrair para um módulo comum seria a fonte única ideal, mas exigiria
  tocar o dashboard fora do escopo da T11; a duplicação é de quatro linhas puras,
  cobertas por teste, e o risco real é baixo. Fica como débito de refatoração
  quando uma terceira tela precisar do mesmo par.
* **E-mail como identificação do autor.** Um e-mail muda e não é um identificador
  estável de pessoa, mas é o rótulo que o produto escolheu para leitura humana; o
  vínculo durável continua sendo o `decidido_por` (UUID) gravado no item.
* **Período interpretado em UTC.** `_inicio`/`_fim` fixam UTC para bater com a
  gravação dos timestamps. Um usuário em outro fuso verá as bordas do dia nesse
  referencial; fuso por empresa é uma decisão transversal, fora desta task.
* **Sem token CSRF.** A página só lê (`GET`), então não introduz superfície nova de
  escrita; a proteção CSRF segue como decisão transversal às rotas `POST`, conforme
  já registrado na T10.

## 4. O que vem a seguir (Roadmap Imediato)

* **T12 (Aceitação F2 + ajustes):** arquivo de aceitação ponta a ponta cobrindo os
  critérios P1/P2 (INC, SUG, APR, ESC, TRA, EDG) com dois tenants e modelo fake, e
  ajuste das suítes que afirmam contratos afetados — é o teste que amarra a jornada
  fila → decisão → trilha num fluxo único.
* **PR de release `feat/f2-hitl → main`:** depois da T12, a integração sobe para a
  `main` com tag de versão, fechando o épico F2.
* **Limite/paginação na trilha:** se o histórico de um tenant crescer, reusar o
  `limite` já suportado por `listar_trilha` com validação `Query`.
* **Fonte única para conversão de período:** extrair `_inicio`/`_fim` de `kpis.py` e
  `correcoes.py` quando surgir a terceira tela com filtro de datas.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio e privacidade:** a trilha é sempre buscada com
  `vinculo.empresa_id` da sessão e o repositório filtra por `empresa_id`;
  `test_historico_isola_outro_tenant` aplica uma correção em cada tenant e confirma
  que o tenant A não enxerga "B1". O guard `exigir_papel(*PAPEIS_APROVADORES)` barra
  `operador` (`test_historico_operador_recebe_403`) e `get_current_user` responde 401
  sem sessão (`test_historico_sem_sessao_recebe_401`). O e-mail do autor só é
  resolvido para ids presentes na própria trilha do tenant.
* **Cobertura e testes automatizados:** `tests/web/test_correcoes.py` passou a ter
  **25 casos** (18 da T10 + 7 novos de histórico), cobrindo listagem com autor,
  filtro de período, inclusão de `falhou`, isolamento por tenant, estado vazio,
  403 e 401. `src/gestlog/web/correcoes.py` e `src/gestlog/repositories/users.py`
  ficaram em **100%** de cobertura. Gate completo: **391 passed**, cobertura total
  **99,06%**, acima do mínimo de 80%.
* **Padrões de qualidade:** `uv run black src/ tests/` → 115 arquivos inalterados;
  `uv run ruff check src/ tests/` → All checks passed. `from __future__ import
  annotations` presente, docstrings e nomes em português, sem comentários fora de
  docstring, sem `print`, funções abaixo de 50 linhas e sem SQL em `web/` (a
  persistência segue confinada a `db/` + `repositories/`).

## Achados corrigidos no self-review

* **Mapeamento de linhas do `UserRepository` reescrito para `dict(...tuples())`
  (introduzido e revertido):** para silenciar um `C416` do ruff, o retorno de
  `emails` foi trocado por `dict(self.session.execute(stmt).tuples())`. O lint
  passou, mas em runtime o resultado quebrou (`TypeError: 'ChunkedIteratorResult'
  object is not subscriptable`) e derrubou os 4 testes de histórico. Revertido para
  o mapeamento explícito `{linha.id: linha.email for linha in ...}`, que é o que
  funciona sobre `Row` do SQLAlchemy; lint e 25 testes verdes na sequência. Lição
  registrada como **L-027**.
* **Docstring do módulo de teste desatualizada (trivial):** `tests/web/test_correcoes.py`
  dizia cobrir apenas `(T10)`; passou a `(T10/T11)`, refletindo os testes de trilha
  adicionados.
* **Sem demais achados** de lógica, tenancy, fronteiras de camada, tipos ou imports;
  nenhuma correção alterou comportamento coberto por teste.
