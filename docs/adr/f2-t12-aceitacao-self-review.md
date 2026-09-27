# ADR: f2-t12-aceitacao

## 1. Contexto & Objetivo

A F2 (HITL) nasceu de uma mudança de natureza do copiloto: ele deixou de ser
read-only e passou a corrigir/completar cadastros, mas somente atrás de uma decisão
humana registrada (AD-002). T1 a T11 construíram a fatia inteira — modelo
`ItemCorrecao` e migration, `CorrectionRepository` escopado por empresa, regras de
completude, sugestões determinísticas, serviço de fila, eventos de auditoria,
aprovação/rejeição, retenção e as telas web de fila/decisão e trilha. Cada task
provou a sua própria fatia com testes de unidade e integração, porém nenhuma delas
exerceu o fluxo **na ordem em que o operador real o usa**. Era possível, por
exemplo, a listagem de incompletos estar correta e a aprovação estar correta sem
que o encadeamento listar → sugerir → decidir → aplicar → auditar → consultar a
trilha tivesse sido exercido ponta a ponta, com dois tenants concorrentes.

O objetivo da T12 é o fechamento de épico: um conjunto de testes de aceitação,
dirigido pelos critérios da `spec.md`, que percorre INC-01..05, SUG-01..05,
APR-01..06, ESC-01..06, TRA-01..03 e EDG-01..10 pela mesma porta que o usuário usa
(HTTP real, banco real, autenticação real), provando que a costura entre as camadas
não se rompeu. O desafio central não é escrever asserções novas, e sim montar um
ambiente fiel ao produto e, ao mesmo tempo, determinístico e offline — sem Ollama,
sem rede e sem vazamento de estado entre cenários — além de manter cada asserção
**ancorada ao que o critério exige**, e não ao que a própria tela produziu.

## 2. Decisões de Arquitetura

**1. Um banco de arquivo por teste, compartilhado entre os engines async e sync**

O produto tem duas stacks de sessão: o engine **assíncrono** (`build_async_engine` +
`init_async_db`) sustenta a autenticação do FastAPI Users, e o **síncrono**
(`build_engine`) sustenta o copiloto, a fila de correções e os repositórios. A
fixture `motores` em `tests/acceptance/conftest.py` cria um SQLite em `tmp_path` e
aponta os dois engines para o **mesmo arquivo**, de modo que ambos enxergam as
mesmas tabelas; a fixture `app` sobrepõe `get_async_session`, `get_sync_session` e
`get_settings` para esse banco temporário. A consequência prática é o isolamento
por empresa deixar de depender de limpeza manual: como o `tmp_path` é único por
teste, cada cenário nasce com um banco limpo, e testar "tenant A não vê B" é
apenas rodar dois fluxos no mesmo teste sem risco de contaminação cruzada.

**2. Modularização por grupo de critério para respeitar o limite de 800 linhas**

Um arquivo único com 37 testes de ponta a ponta estouraria o teto de 800 linhas do
repositório e transformaria uma falha em ruído de leitura. A entrega foi então
fatiada por **família de critério**, cada arquivo com uma responsabilidade
narrativa: `test_f2_hitl.py` cobre a entrada (INC, listar incompletos; SUG, sugerir
valores), `test_f2_hitl_decisao.py` cobre o núcleo do HITL (APR, decidir na fila;
ESC, aplicar e auditar), `test_f2_hitl_trilha.py` cobre conformidade e bordas (TRA,
trilha; EDG, casos-limite) e `test_f2_hitl_chat.py` cobre a garantia transversal do
AD-002 (o chat permanece read-only). O nome do teste carrega o id do critério
(`test_inc_02_...`, `test_esc_04_...`), o que transforma a matriz de rastreabilidade
da spec em algo executável: ao rodar a pasta, a saída lista literalmente a
cobertura, e uma falha aponta o critério quebrado sem exigir leitura do corpo.

**3. Helpers em `f2_suporte.py`, coletados apenas uma vez e sem prefixo `test_`**

Os quatro arquivos compartilham o mesmo repertório: onboarding de conta, login por
cookie, convite de usuário, semeadura de estoque, leitura de item, geração da fila,
busca de item e o par "aprovar pela web". Repetir isso em cada arquivo convidaria
divergência silenciosa — bastaria um deles semear o campo errado para o resultado
variar. Os helpers foram concentrados em `f2_suporte.py`, que **não é coletado pelo
pytest** justamente por não começar com `test_`; os arquivos o importam como módulo
de apoio. O nome é único no repositório, evitando o "import file mismatch" que já
nos custou tempo quando dois arquivos de teste dividiam o mesmo basename sem
`__init__.py` (L-018).

**4. Fluxos de aceitação por HTTP; bordas sem porta HTTP chamam o serviço e o banco**

A maioria dos critérios é exercida pela porta real do usuário: `/onboarding`,
`/auth/login`, `/empresa/convites`, `GET /correcoes`, `POST /correcoes/{id}/decisao`,
`GET /correcoes/historico` e `/chat/stream`. Quatro verificações, porém, ou não têm
endpoint exposto ou precisam de um estado que a rota não produz de propósito: EDG-04
(duas decisões no mesmo item, simuladas chamando `CorrectionService.aprovar` duas
vezes), EDG-05 (sugestão igual ao valor atual, com o item montado direto e o
`upsert` instrumentado), ESC-04 (falha de escrita, com `StockRepository.upsert`
substituído por um erro via `monkeypatch`) e ESC-05/ESC-06 (alvo e item cross-tenant
montados no banco). Isso é deliberado: a concorrência real é comportamento do
serviço, a falha de escrita é uma condição de infraestrutura e forçar um endpoint
para essas bordas aumentaria a superfície de API sem valor de produto. O teste
continua ponta a ponta no que importa — serviço real, banco real, transação real — e
a ADR registra a fronteira em vez de escondê-la.

**5. Read-only do chat afirmado pelo conjunto exato de tools, não por amostra**

O risco estrutural do AD-002 é uma tool de escrita ser vinculada ao loop ReAct e o
LLM poder mutar cadastros sem decisão humana. Para que a garantia seja de
**conjunto**, e não de amostra, `test_chat_read_only_sem_tool_de_escrita` instancia
cada especialista com o `FakeChatModel` e afirma igualdade exata entre
`{tool.name for tool in model.bound_tools}` e o conjunto canônico esperado
(`TOOLS_ESTOQUE`, `TOOLS_TRANSPORTE`, `TOOLS_FORNECEDORES`). Igualdade de conjunto
falha tanto por uma tool a mais (uma escrita indevida) quanto por uma a menos (uma
regressão de vínculo), o que uma asserção por pertencimento não capturaria. O
complemento `test_chat_turno_nao_gera_eventos_de_correcao` percorre um turno real de
`/chat/stream` e confirma que nenhum evento `correcao_*` aparece na auditoria —
provando que a escrita vive fora do loop do LLM, na rota de decisão.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **SQLite de arquivo em vez de Postgres:** os testes de aceitação rodam no dialeto
  local, não no banco de produção. É o compromisso que mantém a suíte hermética e
  veloz (CI sem serviço externo); diferenças de dialeto — janelas, tipos de data,
  locks — ficam fora. O risco é mitigado porque a suíte de integração por task já
  cobre os repositórios, e a T12 é sobre costura de fluxo, não sobre sintaxe SQL
  específica de Postgres.
* **Bordas testadas no serviço, não no HTTP:** EDG-04, EDG-05, ESC-04 e ESC-05/06
  não atravessam a rota, como explicado. A concessão é aceitável porque o serviço é
  exatamente a camada que decide esses comportamentos; a rota apenas traduz o erro
  de domínio em status (404/409/422). Se o produto evoluir para expor essas bordas
  (ex.: um botão de "forçar reaplicação"), os testes migram naturalmente para HTTP.
* **Read-only provado no binding, não no efeito:** o teste confirma que nenhuma
  tool de escrita está vinculada aos nós; a garantia de que as tools existentes não
  escrevem no catálogo continua nos testes de unidade de `tests/test_tools.py`. É
  uma divisão de profundidade consciente: a T12 afirma a **estrutura** (AD-002), a
  unidade afirma o **comportamento** de cada ferramenta.
* **Retenção dependente de `created_at` e de uma empresa com prazo curto:** EDG-10
  força `retention_days = 30` e envelhece `created_at` dos itens, porque a purga
  corta por criação, não por decisão. Isso alinha o teste ao design, mas significa
  que ele não cobre o cenário em que um item antigo é decidido hoje; esse caso é
  coberto pela integração da T9. A escolha evita `sleep` e mantém o determinismo.
* **Três tenants coexistindo no mesmo teste:** `test_tra_02` cria A e B no mesmo
  banco e confirma que o histórico de A não mostra o item B, provando o isolamento
  como parte do próprio fluxo (e não como teste à parte). O custo é um cenário mais
  longo, aceitável para um teste de aceitação.

## 4. O que vem a seguir (Roadmap Imediato)

* **Code review e PR da T12:** a task entra no `code-reviewer` e, em seguida, em um
  PR de `feat/f2-t12-aceitacao → feat/f2-hitl` (nunca contra `main`), com
  `tasks.md` e os testes no mesmo PR e CI verde.
* **PR de release da F2 (`feat/f2-hitl → main`) + tag:** com a F2 fechada, o épico
  sobe de integração para `main` num PR de release único, com a versão a definir.
* **Border hardening (herdado):** rate limiting (AD-015), convite por token,
  empresa ativa e alinhamento de `Membership.user_id` (`Uuid`) a `User.id` (`GUID`)
  — dívidas registradas em AD-027, não pertencem a esta task de testes.
* **Relatórios/gráficos/tabelas:** próximo incremento de produto; a base de
  aceitação criada aqui (app + banco temporário + fake model) é reutilizável para
  os fluxos de leitura agregada.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio e privacidade:** `test_inc_01`/`test_inc_03` criam dois
  tenants e confirmam que a fila de A não mostra o registro de B; `test_apr_06`
  confirma 404 ao decidir item de outro tenant; `test_esc_05` confirma que o alvo
  cross-tenant é recusado sem alterar os dados de B; `test_esc_06` afirma o
  **conjunto exato** de chaves do `detalhe` da auditoria (`item_id`, `tipo`,
  `alvo_chave`, `campo`, `valor`) e que `justificativa` (texto livre) não é
  levada, com o valor truncado em 255 caracteres. `test_chat_turno_nao_gera_eventos_de_correcao`
  confirma que o turno de chat só produz eventos `pergunta`/`recomendacao`. Nenhum
  teste toca a rede: o modelo é o `FakeChatModel`, o banco é arquivo local.
* **Cobertura e testes automatizados:** 37 testes de aceitação da F2 distribuídos
  em 10 INC/SUG, 12 APR/ESC, 13 TRA/EDG e 2 de chat/AD-002. Execução focada:
  `uv run pytest tests/acceptance/ --no-cov -q` → **57 passed** (inclui os 20 da
  F1). Suíte completa: **429 passed**, cobertura **99,06%** (gate de 80%).
* **Padrões de qualidade:** `uv run black --check tests/acceptance/` inalterado e
  `uv run ruff check src/ tests/` → All checks passed. Os arquivos respeitam
  `from __future__ import annotations`, docstrings em português, sem comentários
  fora de docstring, sem `print` e funções bem abaixo de 50 linhas; `f2_suporte.py`
  e `conftest.py` ficam fora da coleta (sem prefixo `test_`).

## Achados corrigidos no self-review

* **Asserção tautológica em APR-05 (baixa):** `assert item_correcao(...)` afirmava
  um objeto ORM sempre truthy (e `scalar_one()` já levantaria se o item não
  existisse), então passaria mesmo que a re-decisão tivesse alterado o estado.
  Substituída por `terminal.decidido_por is not None`, ancorada ao estado decidido.
* **Símbolo solto em SUG-05 (baixa):** `assert "—" in pagina.text` casaria com um
  em-dash em qualquer ponto do HTML. Trocada por `"<td>—</td>" in pagina.text`,
  ancorada à célula do valor atual que o critério pede para distinguir.
* **Sem achados** de dependência de rede, aleatoriedade não semeada, ordem entre
  testes, segredo hardcoded, vazamento entre tenants, `print` ou violação de lint e
  formatação.
