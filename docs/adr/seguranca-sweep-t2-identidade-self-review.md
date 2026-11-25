# ADR: seguranca-sweep-t2-identidade

## 1. Contexto & Objetivo

A varredura do épico **seguranca-sweep** apontou que a superfície pública de
identidade — cadastro da empresa (`/cadastro`, `/onboarding`) e convites —
tratava e-mail como texto literal: `Ana@X.com` e `ana@x.com ` eram duas
identidades distintas (**I-1**), um `POST /cadastro` em rajada não tinha freio
(**I-2**), convidar um e-mail registrado devolvia `409` — um enumerador de quem
já tem conta (**I-3**) — e toda conta nascia com `is_verified=True`, um cargo de
confiança que ninguém conferiu (**I-4**). A T2 fecha os cinco requisitos
**IDT-01..05** e os edge cases **EDG-05/06/08**, sem abrir escopo de produto:
nenhuma rota hoje exige verificação de e-mail, então a conta pode nascer "não
verificada" sem quebrar fluxo algum (decisão humana 3).

O desafio arquitetural central: tornar a unicidade case-insensitive **nos dois
dialetos** (SQLite e Postgres) sem duplicar a fonte de verdade do e-mail, e
recusar duplicatas pré-existentes **antes** de criar o índice — um ambiente com
dado sujo precisa de diagnóstico acionável, não de uma migração morta.

## 2. Decisões de Arquitetura

**1. Normalização como responsabilidade do caso de uso, com um único helper
(IDT-01)**

`normalizar_email(email)` (`strip` + `casefold`) em `auth/accounts.py` é o único
ponto de verdade: `_por_email` compara normalizado, `_novo_usuario` persiste
normalizado (cobre `criar_conta` E `aceitar_convite` — o aceite herda o e-mail
já canônico do convite), e `criar_convite` grava o canônico em `Convite.email`.
Os schemas (`ContaCreate`/`ConviteCreate`) continuam recebendo `EmailStr`
intacto — normalizar no schema multiplicaria pontos de verdade; normalizar no
caso de uso significa que QUALQUER caminho que grave `User` ou `Convite` nasce
canônico. Dado antigo não normalizado no banco não vira falso negativo: a
comparação (`_por_email`) normaliza a ENTRADA, e o índice funcional (abaixo)
garante o banco contra corridas. No login, o caminho é o do FastAPI Users:
`SQLAlchemyUserDatabase.get_by_email` filtra `func.lower(coluna) ==
func.lower(entrada)` — comparação case-insensitive feita no BANCO, não em
Python, então o `casefold` do cadastro e o `lower` do login concordam no dialeto
(limite exótico documentado nas limitações).

**2. Índice único FUNCIONAL em `lower(email)`, não coluna normalizada (IDT-02)**

`User` ganha `__table_args__` com `Index("uq_user_email_ci",
func.lower(cls.email), unique=True)` via `@declared_attr.directive` — o usuário
do adapter do FastAPI Users é o MESMO modelo, então a unicidade vale para todo
INSERT, inclusive caminhos internos do framework que nós não controlamos. A
alternativa (coluna `email_normalizado`) duplicaria a fonte de verdade e exigiria
sincronização em cada gravação + no update de e-mail do FastAPI Users; o índice
funcional é imutável por construção e vale nos dois dialetos (SQLite ≥ 3.9 e
Postgres emitem `CREATE UNIQUE INDEX uq_user_email_ci ON "user" (lower(email))`).
O mesmo modelo declara o índice e a migração o cria — autogenerate do Alembic
ignora índices de expressão, então `f2b3c4d5e6f7` (down `f1a2b3c4d5e6`) é
escrita à mão, padrão do repo. A matriz de dialetos do CI (job `postgres`) prova
o round-trip e a `IntegrityError` no INSERT colidente nos dois dialetos.

**3. Migração fail-fast com conflitos acionáveis (IDT-02, decisão humana 4)**

`upgrade()` consulta `SELECT lower(email) FROM "user" GROUP BY lower(email)
HAVING count(*) > 1` ANTES de criar o índice; havendo conflito, `RuntimeError`
aborta o upgrade listando os e-mails (já na forma canônica) — um ambiente sujo
não migra e o operador sabe exatamente o que resolver. Procedimento de resolução
manual:

1. **Diagnóstico** — `alembic upgrade head` já imprime a lista; para conferir,
   rode no banco: `SELECT lower(email), count(*) FROM "user" GROUP BY
   lower(email) HAVING count(*) > 1;`.
2. **Escolher a forma canônica e deduplicar** — cada grupo é UMA identidade
   real: mesclar vínculos (`membership`), conversas e auditoria do usuário
   redundante para o sobrevivente e REMOVER o duplicado (`DELETE`), ou
   `UPDATE "user" SET email = '<canonico>' WHERE email = '<variante>';` quando
   não houver colisão de linha idêntica. Verificar também `convite.email`
   pendente com a mesma variante (recusar/anular o convite órfão).
3. **Reexecutar** — `alembic upgrade head` (a checagem roda de novo e passa
   limpa).

*Janela de lock no Postgres:* o `CREATE UNIQUE INDEX` (sem `CONCURRENTLY`)
trava escritas na tabela `user` durante a construção. Aceito e assumido no
spec: tabela pequena (usuários de um tenant logístico), janela curta — a
complexidade de `CONCURRENTLY` (transação própria, sem rollback de lote)
não se paga aqui.

**4. Rate limit no cadastro com chave montada na chamada (IDT-03)**

`POST /cadastro` ganha `dependencies=[Depends(limitar("cadastro"))]` — o
I-2 do review anterior (chave do limitador resolvida fora da dependência)
fica resolvido sem registro: `limitar` é uma closure que monta
`"cadastro:<ip>"` DENTRO da dependência, por requisição, lendo
`get_settings` na hora — o `GET` da página continua livre (teste prova 200
após o 429 do POST) e o singleton `limitador` continua isolado por teste
via fixture autouse `_rate_limit_limpo`.

**5. Decoy: resposta indistinguível e token inutilizável (IDT-04/EDG-06)**

A rota `convidar` captura `ConviteDuplicadoError`, loga em `WARNING` e devolve
**201** com `{"email", "papel", "token"}` — o token é `secrets.token_urlsafe(32)`
gerado na hora e NUNCA persistido, então o aceite o recusa por
`_convite_valido` → 400 "Convite inválido, expirado ou já utilizado" — a MESMA
resposta de qualquer token inválido; não existe caminho que distingua decoy de
token real a partir da resposta HTTP. A decisão de negócio (levantar
`ConviteDuplicadoError`) continua no caso de uso `criar_convite`; a rota só
traduz para resposta — e o guard de `aceitar_convite`
(`ConviteEmailRegistradoError`, defesa de takeover da L-048/AD-015) fica
**intocado**: a mudança genérica vale apenas para a CRIAÇÃO de convite
(EDG-08). O warning inclui o e-mail — log INTERNO de servidor (design §T2
explicitamente aceita; a resposta HTTP nunca o revela). Testes provam: 201 +
mesma shape de e-mail novo, decoy não aceita, e o cenário cross-tenant do
code review (atacante convidando a vítima de outro tenant) termina com a
credencial da vítima intacta.

**6. Contas nascem `is_verified=False` (IDT-05)**

`_novo_usuario` troca `True` → `False`: vale para cadastro E aceite de convite
(são os únicos caminhos de nascimento de conta). Seguro porque
`current_active_user = authenticator.current_user(active=True)` — **nenhuma**
dependência pede `verified=True`; o teste de integração prova o ciclo completo
(cadastro → `is_verified=False` no banco → login 204). A migração da T2 não
toca `is_verified` de dado existente (nada de backfill: quem já era
"verificado" por acidente continua, sem mudança silenciosa de estado).

**7. Desvio validado: `fileConfig(..., disable_existing_loggers=False)` em
`alembic/env.py`**

Comportamento padrão do `fileConfig` é `disable_existing_loggers=True`: na
primeira migração rodada DENTRO da sessão de testes (os testes de migração
rodam `command.upgrade` na ordem alfabética ANTES de `tests/web/`), o Alembic
desabilitava todo logger já criado — inclusive `gestlog.web.onboarding`,
importado por testes anteriores — e o `caplog` do teste do IDT-04 deixava de
capturar qualquer warning dele, independentemente de ordem de arquivo. A
correção (`disable_existing_loggers=False`) preserva os loggers existentes;
não silencia log legítimo em runtime de produção: o `alembic.ini` continua
instalando os handlers/loggers do próprio Alembic via `fileConfig`, e loggers
de aplicação simplesmente não são alvo dessa configuração — eles só perdiam
vida, nunca ganhavam saída. Decisão: **manter o desvio**; é correção de causa
raiz (configuração de logging agressiva), não capota de teste.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **A resposta de conflito salta o `commit` (tempo).** O caminho de e-mail
  registrado faz um `SELECT` a menos de gravação — sem `INSERT`/`commit` — e
  pode ser marginalmente mais rápido que o de sucesso; medir isso por timing é
  oráculo frágil (jitter de rede/DB) e o spec exige status/shape idênticos,
  não tempos idênticos. Aceito.
* **`casefold` (Python) vs `lower` (banco) divergem em Unicode exótico.** Para
  `İ`, `ß` e afins, o cadastro canônico (`casefold`) e a busca do login
  (`lower` no dialeto) podem discordar — ex.: `straße@x.com` persiste como
  `strasse@x.com`, e logar com `straße@x.com` falha. Conjunto de e-mails
  reais afetado é ínfimo; a alternativa (`lower()` no helper) deixaria o
  cadastro case-insensitive fraco em demais casos. Aceito e documentado.
* **Migração fail-fast é deliberadamente chata.** Um ambiente com duplicatas
  não migra até resolução manual — o custo cai no operador, o benefício é
  corrigir o dado na fonte em vez de esconder a segunda identidade. Alternativa
  (dedup automático) decide qual conta sobrevive sem contexto de negócio.
* **Log de WARNING carrega o e-mail do conflito.** Log interno; sem ele, o
  operador não diagnosticaria o evento (o HTTP não fala nada). Redigir o log
  (ex. `[EMAIL]`) é follow-up natural se a política de logs endurecer (T3
  já cria a redação de PII — avaliar lá).

## 4. Limitações Conhecidas

* **Enumerabilidade residual do cadastro:** `/cadastro` e `/onboarding` ainda
  respondem "E-mail já cadastrado" (400/409) para e-mail registrado — decisão
  de UX do cadastro (o usuário precisa saber por que falhou); o anti-enumeração
  do IDT-04 vale para CONVITES, onde a enumeration revela relações entre
  empresas. Mudança genérica para cadastro exigiria redesenho de fluxo (decoy
  de cadastro cria empresa fantasma).
* **Divergência Unicode exótica** `casefold` vs `lower` (ver trade-off acima).
* **Rate limit continua in-memory por processo** — sob réplicas, o limite vale
  por instância; o spec desta task não exige store compartilhado (backlog já
  registrado no CONTEXT.md).
* **Tabela de rastreabilidade do spec permanece `Pending`** para IDT-01..05:
  convenção do épico (as linhas da T1 — QUO-01..06 — também estão `Pending`);
  o status é virado no fechamento do épico, não por task.

## 5. Validação de Qualidade e Segurança

* **Discriminante provado contra a versão vulnerável:** revertendo
  temporariamente `web/onboarding.py` para `684dbf4` (base) e rodando a suíte
  focada, `test_convidar_email_registrado_responde_como_novo_e_nao_aceita_decoy`
  falha com `409 != 201` — a versão antiga enumera; a nova, não. Revertido de
  volta com working tree limpa (host git, L-055/L-053 aplicadas).
* **Gate completo (WSL2):** `uv run pytest` → **641 passed, 3 skipped**,
  cobertura **99,09%** (gate de 80%); `ruff check src/ tests/ alembic/` → All
  checks passed; `black --check` → 153 files unchanged. Nenhum teste toca
  rede/Ollama; migrações rodam sobre banco Postgres descartável por teste
  (`CREATE DATABASE`/`DROP ... FORCE` no teardown — sem vazamento de linhas,
  lição I-1 do PR #81).
* **Padrões AGENTS.md:** `from __future__ import annotations` em todos os
  arquivos do diff, funções abaixo de 50 linhas, docstrings em português, sem
  comentários fora de docstring, `logger` sem `print`, SQL da migração
  confinado ao `alembic/`.

## Achados corrigidos no self-review

* **Corrida de unicidade no `/onboarding` devolvia 500 (moderado):** a rota
  pública da API capturava só `UserAlreadyExists`; com o índice funcional da
  T2, a corrida case-divergente (`Ana@X.com` vs `ana@x.com` em dois cadastros
  simultâneos) estourava `IntegrityError` sem handler — a rota web
  `/cadastro` já devolvia 409, a API, 500. Adicionado handler com
  `rollback()` + 409 e teste discriminante
  (`test_onboarding_corrida_de_email_retorna_409`, `3550264`); lição L-056
  registrada.
* **Sem demais achados:** nenhuma falha lógica fundamental, nenhuma violação
  de fronteira (SQL só em `alembic/` + `libs`), nenhuma janela de oracle na
  resposta do decoy, migração com round-trip e fail-fast provados, e o desvio
  do `env.py` validado com raciocínio próprio (§2.7) em vez de aceito pelo
  relatório do builder.
