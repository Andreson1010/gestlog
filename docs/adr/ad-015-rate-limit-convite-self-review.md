# ADR: ad-015-rate-limit-convite

## 1. Contexto & Objetivo

A AD-015 (2026-09-13) registrou duas dívidas de segurança herdadas do MVP: rotas
abertas (`/auth/login`, `/onboarding`, `/empresa/convites`) sem qualquer limite de
taxa — um brute force de senha podia tentar quantas combinações quisesse — e um
fluxo de convite em que **o admin escolhia a senha do convidado**, que então
precisava ser compartilhada por fora (e-mail, mensagem, planilha): senha
conhecida por duas pontas, sem rastro de quem a definiu, e o "convite" era, na
prática, um `Membership` criado com credencial fabril. O objetivo desta entrega é
fechar as duas dívidas sem introduzir infraestrutura nova: um rate limiting que
funcione num processo só (o deploy atual) e um convite em que o admin deixa de
escolher a senha do convidado.

## 2. Decisões de Arquitetura

**1. Rate limit como dependência de router, não middleware global**

O limite mora em `web/rate_limit.py` como dependência FastAPI anexada ao grupo:
`include_router(dependencies=[Depends(limitar("auth"))])` em `/auth/*` e
`APIRouter(dependencies=[Depends(limitar("onboarding"))])` no onboarding. Um
middleware cobriria tudo de uma vez — inclusive rotas internas de leitura
autenticada — e o 429 por excesso de uso legítimo derrubaria o produto inteiro;
a dependência restringe o freio às superfícies **abertas** (login, criação de
conta, convite, aceite), exatamente as que um atacante toca sem sessão. A janela
é deslizante (`deque` de marcas de `time.monotonic()` por chave
`grupo:ip`, sob `threading.Lock`), não fixa: na janela fixa, um atacante enche a
cota no fim do período e recomeça em cheio no instante seguinte; na deslizante,
as marcas expiram uma a uma e o custo da repetição é contínuo. O relógio é
monotônico, então ajustar o relógio do processo não reinicia janelas.

**2. Uso de memória contido: teto rígido com poda por marca viva**

A chave é `grupo + IP`, e a origem vem de `request.client.host` — **sem** confiar
em `X-Forwarded-For`, spoofável diretamente contra a aplicação. A premissa é a
app **exposta diretamente** (deploy atual, sem proxy de terminação): atrás de
reverse proxy, `client.host` vira o IP do proxy para todos os clientes e o
limite por IP degenera num freio global — quando houver proxy, configurar
`uvicorn --proxy-headers --forwarded-allow-ips` e consumir o cabeçalho só de
origens confiáveis. A consequência que o primeiro desenho ignorava era o
crescimento do dicionário: cada IP novo criava uma chave que ninguém mais
removia, e o gatilho é justamente tráfego na rota pública — exaustão de memória
como efeito colateral do rate limiting. A contenção é **rígida** e roda **antes**
do `setdefault` (executar depois era um bug que o teste novo capturou: a chave
da requisição corrente era podada no meio da própria contagem e a tentativa se
perdia — detalhado nos achados): primeiro removem-se, sob o mesmo lock, as
chaves sem marca viva (deque vazio ou última marca mais velha que a janela);
persistindo o teto porque todas estão vivas na janela, a chave mais antiga (ordem
de inserção do dict) é evictada. Com janelas de tráfego acima do teto, um IP que
esteja nela há mais tempo tem suas marcas perdidas e recomeça a contar — costa
aceitável em troca do teto garantido; a janela de risco real (IP ativo com
tráfego de brute force contínuo) é a mesma que justifica o freio. O teto é
constante de módulo justamente para o teste apertá-lo (`monkeypatch`) sem mexer
em produção; `test_limitador_evicta_mais_antiga_quando_todas_vivas` fixa o ramo
sem chaves mortas.

**3. Convite por token: o token em claro nunca toca o banco**

`criar_convite` gera `secrets.token_urlsafe(32)` (32 bytes de entropia), persiste
**apenas o SHA-256 hex** em `convite.token_hash` (coluna `unique`) e devolve o
token somente no retorno da chamada — quem o perde ali não o recupera, porque ele
não existe em repouso: um vazamento do banco não rende convites aproveitáveis. O
aceite (`aceitar_convite`) busca por hash, exigindo `usado_em IS NULL` **e**
`expira_em > agora`, e quem aceita define a própria senha
(`ConviteAceiteCreate`) **criando a conta nova**. A regra de segurança é
definitiva: **o convite nunca toca a credencial de um usuário global existente**
— o token vive em poder do CONVIDADOR (a entrega por e-mail é futura), logo não
comprova posse do e-mail; redefinir a senha de um `User` já registrado
possibilitaria takeover de conta entre tenants (achado CRITICAL do code review).
`criar_convite` portanto só emite para e-mail **não** registrado: e-mail que já
tem conta — em qualquer empresa — devolve 409 na criação, e mesmo que um convite
para esse e-mail apareça no banco (gravado à mão em teste, bug futuro), o
`aceitar_convite` recusa com `ConviteEmailRegistradoError` → 400
(defense-in-depth). Para vínculos de usuários existentes, o caminho futuro é o
aceite autenticado: o próprio usuário, logado, confirma o vínculo. A dupla
aceitação concorrente é fechada pela `UniqueConstraint(user_id, empresa_id)` do
`Membership`: o segundo `commit` bate na unicidade e o `IntegrityError`
capturado na rota vira 409. Convite inexistente, expirado ou já usado é um único
400 — não distinguir "expirado" de "inexistente" impede enumerar tokens válidos
pela resposta.

**4. Contrato: a senha sai do payload do admin**

`ConviteCreate` perde `senha` (fica `email` + `papel`, papel limitado ao enum
`Papel`) e nasce `ConviteAceiteCreate` (`token`, `senha` 8–128). O contrato
quebrou em três pontos, todos corrigidos no mesmo PR: o endpoint de convite, os
dois suportes de aceitação (`f2_suporte`, `relatorios_suporte`) e o `test_acc_03`
da F1 — o helper `convidar()` dos suportes agora encadeia convite → aceite com a
senha padrão de teste, então nenhum teste de aceitação precisou saber do
protocolo de token além da chamada do helper. Convite para e-mail (vinculado à
empresa ou registrado em outra) levanta `ConviteDuplicadoError` → 409 **antes** de
gastar um token — inclusive o self-convite do próprio admin.

**5. Migração `e8a1c5d9f3b7` com round-trip de teste**

`upgrade` cria `convite` (8 colunas, FK para `empresa`, unique em `token_hash`);
`downgrade` derruba. Como a migração não transporta dado, a simetria é o
critério — e ganhou teste em `tests/test_migrations.py`: tabela e conjunto de
colunas no head, ausência após `downgrade` à revisão anterior e retorno no
re-upgrade (a regra da L-037 no seu caso aplicável: round-trip nos dois sentidos,
ainda que sem dado a validar por coluna).

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **Rate limit por processo, não compartilhado:** em memória basta no deployment
  atual (um processo web); com réplicas, o limite real é `réplicas × 5/60 s` e as
  marcas não são compartilhadas. A interface (`permitir(chave, limite, janela)`)
  é a única fronteira a trocar por Redis sem tocar rotas — a troca é caminho de
  escala declarado, não escolha definitiva.
* **5 tentativas por 60 s por IP é apertado para uso humano atrás de NAT**
  (escritório num único IP público fazendo login). O valor é `Settings`
  (`rate_limit_tentativas`/`rate_limit_janela_segundos`), então afrouxar por
  ambiente é env, não código. O que se compra é o freio ao brute force de
  credencial, vetor original da dívida.
* **Sem entrega de token por e-mail:** o token volta na resposta do
  `POST /empresa/convites` para o admin repassar manualmente. Enquanto a
  integração de notificações não existir, o risco é o token escapar no canal
  manual; compensações: uso único e validade de 7 dias
  (`convite_validade_dias`), então a janela de abuso é curta.
* **Múltiplos convites pendentes do mesmo e-mail são permitidos:** não há unique
  em `(empresa_id, email)` entre convites pendentes; cada um gera token válido
  até o primeiro aceite (os demais morrem com o `usado_em`). O spam de convites
  é tangenciado pelo rate limit do router (5/min/IP), não por regra de negócio
  própria.
* **Reconvite de e-mail já vinculado devolve 409, não 200 silencioso:**
  intencional, para o admin saber que nenhum token foi emitido.

## 4. O que vem a seguir (Roadmap Imediato)

* **Entrega do token por e-mail** (integração de notificações): remove o último
  toque manual do fluxo e fecha a história do convite.
* **Store compartilhado (Redis) ao escalar réplicas:** troca do backend de marcas
  sem furar o contrato de `limitar`/`RateLimiter`.
* **Estado nomeado do convite:** um status (pendente/usado/expirado) além de
  `usado_em` tornaria a auditoria de convites uma consulta direta; hoje a
  auditoria via `AuditLog` cobre rotas autenticadas, mas não o aceite público.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio e privacidade:** nenhum teste toca rede/Ollama; o token
  em claro não é persistido nem logado; o hash em repouso neutraliza dump do
  banco; o 429 não discrimina qual limite foi atingido; os detalhes de erro
  permanecem genéricos ("Usuário já vinculado à empresa" não revela de quais
  empresas um e-mail é membro).
* **Cobertura e testes automatizados:** `tests/web/test_rate_limit.py` cobre a
  janela (limite exato, isolamento por chave, expiração via relógio injetado,
  429 ponta a ponta, limite lido do `Settings`) e a poda;
  `tests/web/test_onboarding.py` cobre convite feliz, 403 sem admin, 409
  duplicado, 400 inválido, expirado e de uso único; o teste de migração cobre o
  round-trip da tabela. Gate completo (WSL): **606 passed, 1 skipped, 99.01%**.
* **Padrões de qualidade:** `black --check` + `ruff check` verdes;
  `from __future__ import annotations`, docstrings e nomes em português, sem
  comentários fora de docstring, sem `print`; funções ≤ 50 linhas e arquivos
  ≤ 800 linhas.

## Achados corrigidos no self-review

* **Poda do rate limiter perdia a tentativa corrente (média):** a poda —
  introduzida nesta revisão para conter a memória — foi primeiro implantada
  **depois** do `setdefault`: a chave da requisição corrente era removida, o
  `append` gravava num deque órfão fora do dicionário e a tentativa não era
  registrada (limite furável). O próprio teste da poda capturou uma segunda
  falha: gatilho `>` sobre o tamanho pré-inserção nunca disparava na borda.
  Correções: poda **antes** do `setdefault` e gatilho `>=`;
  `test_limitador_poda_chaves_sem_marca_viva` cobre o comportamento final.
* **Crescimento sem limite do dicionário de marcas (média):** achado que motivou
  a poda: uma rota pública limitada por IP não pode crescer memória sem teto com
  o tráfego que ela própria atrai.
* **Guard 400 de `empresa_id` inválido sem teste (baixa, D6):** a rota
  `POST /empresa/ativa` rejeitava UUID malformado com 400 e nenhum teste
  exercitava o ramo; adicionado `test_troca_com_empresa_id_invalido_e_recusada`.
* **Fixture de teste tipada contra o padrão (baixa, D6):**
  `motor_async(tmp_path: object)` + `# type: ignore[attr-defined]` em
  `tests/web/test_empresa_ativa.py`; corrigido para `tmp_path: Path`, como no
  restante de `tests/web/`.

## Achados endereçados no code review independente

* **Takeover de conta entre tenants (CRITICAL, bloqueante):** o aceite original
  redefinia a senha global de e-mail já registrado — e o token é entregue ao
  CONVIDADOR, não ao convidado, logo qualquer pessoa que criasse uma empresa por
  `/onboarding` podia convidar o e-mail da vítima, receber o token e redefinir a
  senha dela. Corrigido na raiz e em camada dupla: `criar_convite` só emite
  convite para e-mail NÃO registrado (409 caso contrário) e `aceitar_convite`
  recusa `ConviteEmailRegistradoError` → 400 sem criar vínculo nem tocar
  senha. Testes novos: convite para e-mail registrado → 409; convite gravado à
  mão no banco com e-mail registrado → recusa + senha global intacta (login
  original continua válido, senha do atacante inválida).
* **429 nunca testado nas rotas reais (média):** os testes cobriam o `RateLimiter`
  e um app sintético; remover o wiring não deixaria a suíte vermelha. Um
  teste por rota real (`/auth/login`, `/onboarding`, `/empresa/convites`,
  `/convites/aceitar`) com limite 1 fixa o `[esperado, 429]`.
* **Teto do limiter não era rígido (baixa):** com todas as chaves vivas, nada era
  removido e o dicionário crescia além de `_MAX_CHAVES`. A poda passa a evictar
  a chave mais antiga (ordem de inserção) até caber a nova; teste fixa o
  comportamento e a ADR registra a degradação de um IP longevo na janela.
* **FK `convite.empresa_id` sem índice (baixa):** índice `ix_convite_empresa`
  adicionado no modelo e na migração (create/drop simétricos) — hoje não há
  consulta por empresa, mas FK não gera índice em Postgres.
* **Coesão de commits D5/D6 (registrada, não corrigida):** o wiring de `/auth`
  e helpers de vínculo ficaram em commits vizinhos do ideal; como o PR é
  squash-mergeado, o histórico final é um commit coeso — a nota fica para
  revisão futura de fatiamento.
* **`/empresa/ativa` fora do rate limit (baixa):** exige autenticação e só
  reordena o próprio vínculo; freio desnecessário, registrado aqui.
* **Constante morta (baixa):** `_COOKIE` não usado em
  `tests/web/test_empresa_ativa.py` removido.
