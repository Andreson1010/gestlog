# ADR: ui-beautifului-t1

## 1. Contexto & Objetivo

A F1 entregou o MVP funcional com CSS cru (cores em `hex`, um único `app.css`
de 191 linhas). Esta feature porta os primitivos visuais do
**beautifului.dev** para a stack existente **Jinja2 + HTMX + SSE**, sem React,
sem Tailwind e sem build de JS. A T1 cobre o *shell* autenticado com sidebar e
o *design system* (tokens, tipografia, raios e sombras); a T2 estiliza o
`login.html` e adiciona a página pública **`/cadastro`**.

O desafio central é modernizar a camada visual **sem regredir** o contrato
atual: páginas ainda não migradas (`chat`, `importar`, `kpis`, `historico`)
dependem das classes legadas do `app.css`, e os testes assertam textos,
atributos e hrefs literais. Qualquer reescrita de markup ou de CSS precisa
preservar esses contratos.

## 2. Decisões Arquiteturais

- **Design tokens isolados em `static/tokens.css` e consumo via `@import` no topo
  de `app.css`.**
  - **Justificativa:** um único ponto de verdade para cor/tipografia/raio/espaço,
    mantendo a folha principal abaixo do teto de 800 linhas. O `@import` na
    primeira linha é CSS válido (precede qualquer regra) e resolve relativo a
    `/static/`, servindo `tokens.css` pelo mesmo `StaticFiles`. Não exige build.
- **Shell autenticado como *default* de `base.html` através de `{% block layout %}`;
  páginas públicas sobrescrevem o bloco com um card centralizado (`.publico` /
  `.cartao`).**
  - **Justificativa:** páginas autenticadas continuam usando apenas
    `{% block conteudo %}` (zero churn em `home/chat/importar/kpis/historico`),
    enquanto `login`/`cadastro` optam por um layout sem sidebar. O bloco troca o
    shell inteiro, não apenas o conteúdo, o que evita condicionais no template.
- **`/cadastro` reutiliza `accounts.criar_conta` e o schema `ContaCreate`, os mesmos
  do `POST /onboarding` (JSON).**
  - **Justificativa:** validação (`nome_empresa` 1–120, `EmailStr`, `senha` 8–128)
    e persistência transacional (empresa + usuário + `Membership` admin no mesmo
    `commit`) ficam em um só lugar. O contrato JSON de `/onboarding` permanece
    intacto, como exigido pelo spec.
- **Handler HTML dedicado ao `POST /cadastro` (form-encoded), separado do router de
  onboarding, com sucesso em `303 → /login`.**
  - **Justificativa:** o endpoint JSON não aceita `application/x-www-form-urlencoded`
    de forma amigável ao navegador. O padrão *POST/Redirect/GET* (303) evita
    reenvio do formulário ao recarregar a página.
- **Campos `Form()` com default `""` e validação delegada ao Pydantic (correção do
  self-review).**
  - **Justificativa:** o FastAPI normaliza string vazia de formulário para `None`
    em campos `Form()` obrigatórios, devolvendo **422 JSON** — o que contraria o
    requisito de "erro re-renderiza o formulário". Com default `""`, todo input
    vazio/curto/longo cai no `ValidationError` tratado e retorna o HTML re-renderizado
    com **400**.
- **Tratamento explícito de `UserAlreadyExists` e `IntegrityError` (com `rollback`).**
  - **Justificativa:** fecha a corrida de e-mail duplicado entre duas requisições
    concorrentes. `criar_conta` verifica o e-mail antes de inserir; se o `commit`
    (ou `flush`) violar a unicidade, o `rollback` desfaz o estado parcial sem deixar
    empresa/usuário órfãos.
- **Inter carregada por Google Fonts (`preconnect` + stylesheet) no `<head>` (correção
  do self-review).**
  - **Justificativa:** `tokens.css` declarava `--font-sans: Inter, …`, mas nenhuma
    origem carregava a fonte, deixando o requisito "Inter font" silenciosamente não
    cumprido em máquinas sem a fonte instalada. O CDN já é usado para HTMX/SSE.

## 3. Trade-offs & Compromissos

- **Folha extra (`tokens.css`):** um request adicional de CSS em troca de tokens
  reutilizáveis e respeito ao teto de linhas. Aceitável — poucos KB, cacheável.
- **Classes legadas preservadas em `app.css`:** a folha reescrita mantém `.form-*`,
  `.tabela-historico`, `.conversa`, `.turno`, `.kpis` etc. para não quebrar páginas
  ainda não migradas. Custa um período de CSS duplicado (tokens novos + legado),
  que some conforme T3–T6 avançam.
- **Google Fonts como dependência externa:** ganha-se a fonte do design system ao
  custo de um terceiro (privacidade/performance) e sem SRI, que o Google Fonts não
  oferece. Coerente com o uso já existente de CDN para scripts; um *self-host* fica
  como evolução futura.
- **`/cadastro` público sem CSRF/rate limit:** aceito e documentado (AD-015). O
  endpoint não depende de cookie/sessão para agir, então CSRF não é um vetor
  relevante; abuso de spam fica como débito já registrado.
- **Status divergente no e-mail duplicado:** caminho comum devolve **400**,
  caminho de corrida (`IntegrityError`) devolve **409**. Ambos re-renderizam o
  mesmo HTML; a divergência é cosmética e proposital (409 = conflito de estado).

## 4. Limitações Conhecidas

- Sem rate limiting nem token CSRF em `/cadastro` (superfície pública de spam já
  mapeada em AD-015).
- O handler de `IntegrityError` devolve "E-mail já cadastrado." para **qualquer**
  violação de integridade; hoje a única unicidade relevante é o e-mail, mas a
  mensagem não distingue outras restrições.
- `.form-periodo` (em `kpis.html`) continua sem estilo dedicado — será tratado na
  T5.
- Acessibilidade mínima: `label`/`for`, `role="alert"` e `aria-live` preservados;
  o contraste dos textos `--ink-3` (placeholder/rodapé) sobre os fundos escuros
  não foi auditado com ferramenta.
- Páginas T3–T6 ainda não migradas visualmente, dependendo das classes legadas.
