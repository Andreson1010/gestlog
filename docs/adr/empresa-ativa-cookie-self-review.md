# ADR: empresa-ativa-cookie

## 1. Contexto & Objetivo

Desde a F1, um usuário com mais de um vínculo (`Membership`) ficava parado na
empresa resolvida de forma determinística — a mais antiga — sem qualquer meio de
trocar de contexto na sessão. O code review da F1 registrou o débito: com
usuários pertencentes a múltiplos tenants, a empresa ativa não é um detalhe
cosmético, é o escopo de **tudo** que resolve por membership — chat, KPIs,
correções, relatórios, admin. Trocar de empresa a cada operação significaria
relogar; a entrega fecha isso com uma seleção que persiste pela sessão sem criar
uma nova entidade de estado server-side.

## 2. Decisões de Arquitetura

**1. Cookie como dica de ordenação, nunca como autorização**

A preferência mora num cookie `gestlog_empresa_ativa` (HttpOnly, `SameSite=lax`,
`secure` herdando `auth_cookie_secure`) gravado por `POST /empresa/ativa`, e os
resolvedores (`get_current_membership`, `get_current_membership_optional`,
`get_current_empresa_optional`) a leem. O ponto essencial: o cookie **só
reordena** a consulta de vínculos do próprio usuário — `_buscar_membership` é
sempre escopada por `user_id` e ordena com `CASE` que prioriza a empresa ativa
sobre `created_at`/`id`. Um cookie forjado para uma empresa em que o usuário não
tem vínculo não muda nada: nenhum vínculo casa com a ordem preferida, a consulta
cai no mais antigo e o 403 de "sem vínculo" segue intacto. Não existe estado de
sessão no servidor para invalidar — a troca de contexto automática (logout de A,
login de B no mesmo navegador) herda um cookie de empresa que B provavelmente não
tem vínculo para usar, e o fallback neutraliza-o sozinho.

**2. Fallback determinístico e silencioso para cookie inútil**

Cookie ausente, malformado (não-UUID) ou presente sem correspondência de vínculo
levam ao mesmo caminho: o vínculo mais antigo, na ordem `(created_at, id)` que já
resolvia antes. Nenhuma destas situações é erro — a sessão continua válida, a
empresa ativa é apenas preferência não atendida. O cookie malformado é ignorado
sem log de erro porque não é incidente: é estado de navegador, não entrada do
usuário. O teste `test_cookie_malformado_cai_no_vinculo_mais_antigo` ancora o
comportamento na empresa exibida, não na ausência de exceção.

**3. Troca explícita revalida tudo, não confia em nada**

`POST /empresa/ativa` recebe o `empresa_id` como formulário, o valida como UUID
(400 se malformado), exige usuário autenticado e **consulta o vínculo na
empresa-alvo** antes de gravar o cookie (403 sem vínculo) — a revalidação a cada
troca é o que mantém o item 1 verdadeiro: o cookie nunca pode conter uma empresa
que o usuário não pôde escolher. O sucesso devolve 303 para `/`, então o seletor
funciona de qualquer página-form que o renderize (hoje, a home), sem JavaScript.
`auth/deps.py` pública `COOKIE_EMPRESA_ATIVA` como constante (reexportada em
`auth/__init__.py`) — o nome do cookie é contrato entre deps, app e testes, não
string espalhada.

**4. Seletor aparece só com múltiplos vínculos, marcado por id**

`home.html` renderiza o seletor somente com mais de um vínculo (usuários de um
tenant só veem ruído). A `home` passa a listar vínculos com a empresa carregada
(`listar_vinculos`, `selectinload` — a consulta passa a rodar em toda visita
autenticada à home) e a marca a opção ativa comparando **ids**, não nomes
(empresas distintas podem ter o mesmo nome; corrigido no self-review, ver
achados).

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **Preferência não sobrevive a dispositivos nem a limpeza de cookies:** é cookie
  de sessão (sem `max_age`), por desenho — empresa ativa é contexto de trabalho
  corrente, não configuração de conta. Persistência cross-device implicaria
  coluna no `User` ou tabela de preferências e fluxo de sincronia; o débito
  registrado não pedia isso.
* **A preferência é global à sessão, não por aba:** duas abas do mesmo navegador
  compartilham o cookie e trocam juntas. Repartir por aba exigiria algo na linha
  de `sessionStorage` + header, com poder novo de autoria no cliente; o valor da
  troca por aba não justifica a superfície de ataque.
* **Páginas que resolvem empresa fora do resolvedor continuam ignorando o
  cookie:** trocar de empresa muda o escopo das rotas que passam por
  `get_current_membership*`; qualquer rota que derive empresa por outro caminho
  (hoje: nenhuma relevante) precisaria aderir depois. O teste da home confirma o
  consumidor principal.
* **Sem endereço "minha conta":** a troca morou na home porque é o ponto de
  entrada do autenticado; uma página de preferências futura pode reusar o mesmo
  endpoint (o contrato 400/403/303 é form-based, não JSON de UI).

## 4. O que vem a seguir (Roadmap Imediato)

* **Indicador de empresa ativa na navegação global** (shell): hoje a home exibe;
  o shell do chat/KPIs não mostra a empresa da sessão em uso.
* **Auditoria de troca de contexto:** um `AuditLog` no `POST /empresa/ativa`
  daria trilha de quem operou em qual tenant quando — barato, e valioso quando
  múltiplos vínculos forem regra (gestores plurais), não exceção.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio e privacidade:** o cookie só é gravado após revalidação
  de vínculo; a leitura sempre escopada por `user_id` impede que a preferência
  atravesse tenants; o cookie malformado não gera erro visível e não altera
  comportamento. Nenhum teste toca rede/Ollama.
* **Cobertura e testes automatizados:** `tests/web/test_empresa_ativa.py` cobre
  resolução sem cookie (vínculo mais antigo), troca com 303 + efeito na home,
  403 sem vínculo, 400 com `empresa_id` malformado e fallback de cookie
  malformado — ancorados no texto renderizado e nos status, não em
  affordances. Gate completo (WSL): **599 passed, 1 skipped, 99.01%**.
* **Padrões de qualidade:** `black --check` + `ruff check` verdes;
  `from __future__ import annotations`, docstrings e nomes em português, sem
  comentários fora de docstring; funções ≤ 50 linhas e arquivos ≤ 800 linhas.

## Achados corrigidos no self-review

* **Opção ativa do seletor marcada por nome de empresa (média):** o template
  comparava `empresa.nome == empresa_nome`; com duas empresas de mesmo nome num
  vínculo duplo, as duas opções apareceriam "ativas" (a primeira, na prática). O
  contexto ganhou `empresa_ativa_id` e a comparação é por `id` — a marcação
  também deixa de depender de campos com HTML que chega escapado pelo Jinja.
* **Guard 400 sem teste (baixa):** ramo `empresa_id` malformado em
  `POST /empresa/ativa` sem cobertura; adicionado
  `test_troca_com_empresa_id_invalido_e_recusada`.
* **Fixture de teste tipada contra o padrão (baixa):** `tmp_path: object` +
  `# type: ignore[attr-defined]` substituído por `tmp_path: Path`, padrão de
  `tests/web/`.
