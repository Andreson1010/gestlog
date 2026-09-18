# ADR: t33-aceitacao-p1

## 1. Contexto & Objetivo

A F1 construiu, task a task, o MVP do gestlog como copiloto read-only: conta e
isolamento por empresa, importação de CSV, chat com os quatro domínios,
recomendação explicada com aceite, redação de PII, retenção/auditoria, qualidade
e quota. Cada task provou a sua própria fatia com testes de unidade e integração,
mas nada garantia que as fatias **funcionassem juntas** na ordem em que o cliente
real as usa. Era possível, por exemplo, o login estar correto e o isolamento do
chat estar correto sem que o fluxo completo — criar conta, importar, perguntar,
ver a recomendação, aceitar — tivesse sido exercido de ponta a ponta.

O objetivo da T33 é justamente esse fechamento: um arquivo único de aceitação
(`tests/acceptance/test_f1_mvp.py`) que percorre os critérios P1 da
`spec.md` — ACC-01..04, ING-01..03, COP-01..06, SEC-01..03 e QUA-01..02 — pela
mesma porta que o usuário usa, a API HTTP, e prova que a costura entre as camadas
(web → copiloto → grafo → repositórios) não se rompeu. O desafio central não foi
escrever asserções novas, e sim montar um **ambiente de execução** que fosse ao
mesmo tempo fiel ao produto (banco real, app real, autenticação real) e
determinístico/offline (sem Ollama, sem rede e sem vazamento de estado entre
testes).

## 2. Decisões de Arquitetura

**1. Um único arquivo, um único app, um banco de arquivo por teste**

O arquivo usa a fixture `motores` para criar um SQLite em `tmp_path` e o compartilha
entre o engine **assíncrono** (`build_async_engine` + `init_async_db`, usado pelo
FastAPI Users) e o engine **síncrono** (`build_engine`, usado pelo copiloto e pela
importação). O motivo é prático: o sistema tem duas stacks de sessão, e um app
`create_app` real espera que ambas enxerguem as mesmas tabelas. Como o
`tmp_path` é único por teste, cada teste nasce com um banco limpo — o isolamento
entre empresas deixa de depender de limpeza manual e passa a ser garantido pelo
setup. A fixture `app` sobrepõe `get_async_session`, `get_sync_session` e
`get_settings` para apontar ao banco temporário, então nenhuma rota toca o
Postgres de desenvolvimento nem conexões implícitas.

**2. O modelo de chat entra por `dependency_overrides`, nunca pela rede**

O critério "sem rede" não é uma promessa verbal: `get_chat_model` é uma
dependência FastAPI memoizada com `lru_cache`, e o arquivo a substitui por
`app.dependency_overrides[get_chat_model] = lambda: model` a cada cenário de chat.
O modelo injetado é o `FakeChatModel` de `tests/conftest.py`
(`fake_model_cls`), que devolve rotas pré-programadas para o supervisor e uma fila
de `tool_calls` para os especialistas. Assim o teste controla com exatidão o
roteamento, a resposta, a justificativa, as fontes, a ausência de base e o número
de tokens — sem chamar Ollama. O grafo é recompilado a cada requisição com esse
modelo (`CopilotService.answer` → `build_graph(model=...)`), o que torna o
override efetivo mesmo havendo `lru_cache` no factory de produção.

**3. Fluxos de aceitação via HTTP; exceções chamam o serviço direto e documentam o porquê**

A maioria absoluta dos critérios é exercida por HTTP real: onboarding, login por
cookie, convite, listagem de usuários, upload e histórico de importação,
`/chat/stream` (SSE), feedback e `/kpis`. Duas verificações, porém, não têm
endpoint exposto na F1: **SEC-02** (retenção) chama `purgar_expiradas(session,
settings=...)` diretamente e **QUA-01** (golden set) chama `run_golden_set(...)`
diretamente. Isso é deliberado: a retenção é uma política executada por rotina
(deploy/cron), não por request do usuário; e o golden set é ferramenta de
avaliação, rodada por script. Inventar um endpoint só para o teste aumentaria a
superfície de API sem valor de produto. O teste continua sendo ponta a ponta no
que importa — o serviço real, com o banco real, escrevendo e lendo as tabelas
reais — e a ADR registra a fronteira em vez de escondê-la.

**4. Nomes de teste por critério para rastreabilidade direta**

Cada teste carrega o ID do critério (`test_acc_01`, `test_ing_02`, `test_cop_04`,
`test_sec_01`, `test_qua_02`). A intenção é transformar a matriz de
rastreabilidade da `spec.md` em algo executável: ao rodar
`pytest tests/acceptance`, a saída lista literalmente a cobertura dos requisitos
P1, e uma falha aponta o critério quebrado sem exigir leitura do corpo do teste. O
helper `_tool_comum` centraliza a chamada de `enviar_resposta_logistica`, fonte
única da resposta logística, evitando duplicar a composição de resposta em cada
cenário de chat.

**5. Estados derivados são medidos no banco, não inferidos do HTML**

Onde a tela renderiza pouca informação, a asserção busca o **estado persistido**:
`test_qua_02` confirma o `UsageRecord` atribuído `empresa_id`-a-`empresa_id` e
`test_sec_03` consulta `AuditLog.evento` diretamente. Isso evita um teste
tautológico do tipo "a página mostra o que a própria página gerou". No fluxo de
aceite, o `test_cop_aceite_registra_decisao_e_historico` reabre `/chat`, extrai o
`recommendation_id` do HTML e confirma que a decisão "aceita" reaparece após o
recarregamento — que é exatamente o *Independent Test* do critério.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **SEC-02 e QUA-01 não atravessam o HTTP:** como explicado, não há endpoint de
  retenção nem de golden set. A concessão é aceitável porque ambos são
  operacionalmente invocados fora do request do usuário; o teste cobre o mesmo
  código com as mesmas dependências reais. Se a F1 evoluir para expor um painel
  de administração de retenção, esses testes migram naturalmente para HTTP.
* **SQLite de arquivo em vez de Postgres:** o teste de aceitação roda no dialeto
  local, não no banco de produção. É um compromisso de velocidade e
  hermeticidade (CI sem serviço externo) que deixa de fora diferenças de dialeto
  — janelas, tipos de data e locks. O risco é mitigado porque a suíte de
  integração por task já cobre os repositórios, e a T33 é sobre **costura de
  fluxo**, não sobre sintaxe SQL específica de Postgres.
* **`test_cop_02` verifica o binding de tools, não o "read-only" em si:** o fake
  expõe `bound_tools` do último especialista montado e o teste confirma
  `consultar_estoque` + `enviar_resposta_logistica`. Provar a ausência de escrita
  por ferramenta exigiria instrumentar cada tool; a garantia real de read-only
  está nos testes de unidade das tools e no desenho da F1. Fica registrado como
  limitação de profundidade, não como lacuna de fluxo.
* **Cobertura excedente ao pedido:** `test_acc_05` (sem sessão → 401/redirect) e
  `test_cop_aceite_registra_decisao_e_historico` (aceite + histórico) vão além de
  ACC-01..04/COP-01..06 porque fecham os critérios de conta/login e do
  *Independent Test* de aceite. Custo baixo, valor de regressão alto; não
  substituem nenhum critério pedido.
* **`test_sec_02` e `test_qua_01` têm ciclos de vida diferentes:** o primeiro
  precisa continuar assíncrono porque consome a fixture assíncrona `motores`; o
  segundo foi tornado síncrono por não ter `await`. A assimetria é intencional e
  está comentada pelo tipo da função, não por comentário de código.

## 4. O que vem a seguir (Roadmap Imediato)

* **F2 — Escrita/HITL (out of scope da F1):** os fluxos de execução de ações
  (reposição, contato com fornecedor, alteração de cadastro) exigirão um novo
  conjunto de aceitação: aprovação humana explícita, idempotência da ação,
  trilha de auditoria da escrita e reversão. A base de aceitação daqui (app +
  banco temporário + fake model) é reutilizável; o que muda é o eixo de
  asserção — de "a recomendação foi apresentada" para "a ação só ocorreu após
  aprovação e é rastreável".
* **Endpoint de retenção/administração:** quando a F1 evoluir para dar ao admin
  controle do prazo de retenção, SEC-02 deve passar a ser exercido por HTTP e o
  teste direto vira regressão do serviço.
* **Golden set como pipeline:** QUA-01 hoje mede o relatório em memória; a
  evolução natural é persistir o relatório por execução e comparar tendência
  entre versões de prompt/modelo, ainda com o runner injetável criado agora.
* **Hardening de CSRF e observabilidade:** herdado das tasks anteriores; não
  pertence ao escopo desta task de testes, mas entra no aceite de release da F1.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio e privacidade:** o teste `test_acc_04` cria dois tenants
  e confirma que a consulta e o histórico de um não vazam para o outro;
  `test_sec_01` inspeciona as mensagens efetivamente entregues ao modelo
  (`model.mensagens_recebidas`) e prova que "João Silva" e o telefone não
  aparecem, apenas o marcador `[NOME]` da redação. O isolamento por empresa é
  ainda verificado indiretamente por toda requisição autenticada — o `tenant_id`
  vem da sessão, nunca do cliente. Nenhum teste toca a rede: o modelo é o fake,
  o banco é arquivo local e a execução usa `-p no:langsmith`.
* **Cobertura e testes automatizados:** o arquivo tem **20 testes** e cobre os IDs
  ACC-01..05, ING-01..03, COP-01..06 (mais aceite/histórico), SEC-01..03 e
  QUA-01..02. Execução focada: `20 passed`. Suíte completa: **248 passed**, com
  **98,26%** de cobertura (gate de 80%), sem falhas de rede.
* **Padrões de qualidade:** `black --check src/ tests/ evals/` → 97 arquivos
  inalterados; `ruff check src/ tests/ evals/` → All checks passed. O arquivo
  respeita `from __future__ import annotations`, docstrings em português, sem
  comentários fora de docstring, sem `print`, sem hardcode de segredo real e
  funções bem abaixo de 50 linhas.

## Achados corrigidos no self-review

* **Parâmetro `app` não utilizado (baixa):** `test_acc_03_convite_da_acesso_com_papel`
  declarava `app: FastAPI` sem usá-lo. Parâmetro removido para manter a assinatura
  fiel ao que o teste consome.
* **`test_qua_01` assíncrono sem `await` (baixa):** o teste do golden set é
  puramente síncrono (`run_golden_set`) e só usa fixture síncrona; foi convertido
  de `async def` para `def`, eliminando uma corrotina desnecessária sob
  `asyncio_mode = "auto"`.
* **QUA-02 não provava atribuição ao tenant (média):** a asserção contava
  `UsageRecord` de forma global e ainda criava uma `Empresa` descartável sem
  relação com o fluxo. O teste passou a resolver o `empresa_id` via
  `_empresa_id(fabrica_sync, "op@qua.com")` e a contar apenas os registros
  daquele tenant, alinhando a asserção ao critério "atribuí-lo ao tenant".
* **ING-03 verificava só o tipo (baixa):** o histórico por tenant afirmava apenas
  que "estoque" aparecia no HTML. Foi adicionada a checagem do status
  `"concluido"`, cobrindo o critério de registrar **status** e contagem, e não só
  a presença do tipo.
* **Sem achados** de dependência de rede, aleatoriedade não semeada, ordem entre
  testes, segredo hardcoded, vazamento entre tenants, `print` ou violação de lint
  e formatação.
