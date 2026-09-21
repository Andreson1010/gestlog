# UI overhaul (beautifului) — tasks

Objetivo: substituir os componentes crus da UI por primitivos no estilo
**beautifului.dev**, mantendo a stack **Jinja2 + HTMX + SSE** (AD-007), e criar a
página pública **`/cadastro`** (empresa + e-mail + senha).

## Decisões (aprovadas)

- **Port, não reescrita**: reimplementar markup/CSS dos primitivos em Jinja2 +
  `static/*.css` (+ HTMX/SSE onde houver interação). **Sem React/Tailwind/build.**
- **Cadastro**: `GET /cadastro` (novo template) + `POST /cadastro` **form-encoded**
  chamando `accounts.criar_conta`; sucesso → **303 para `/login`**. O
  `POST /onboarding` (JSON) **não muda** (contrato coberto por testes/aceitação).
- **Admin**: nova página HTML mínima `/admin/usuarios` (lista + alterar papel +
  remover), sob `exigir_papel("admin")`, com endpoints form-encoded novos;
  a API JSON `/empresa/usuarios*` permanece.
- **CSS**: dividir `static/app.css` em vários arquivos (teto de 800 linhas);
  HTMX/SSE seguem via CDN com SRI (assertado em `tests/web/test_app.py:22`).
- **Entrega**: branch de integração `feat/ui-beautifului`; 1 PR por task;
  self-review (ADR) + code review por task.

## Tarefas

- [x] **T1 — Shell + design system (base.html + CSS)**
  - Tokens (cores, tipografia, espaçamento), split do CSS, `base.html` com
    **sidebar nav** e `{% block %}` para shell autenticado vs público.
    Inter carregada via Google Fonts (preconnect + stylesheet no `<head>`).
  - Preservar hrefs `/`, `/importar`, `/chat`, `/kpis`; adicionar `/cadastro`
    (público) e `/admin/usuarios` (admin).
- [x] **T2 — Login + Cadastro**
  - Reestilizar `login.html` (card/inputs primitivos) mantendo `hx-post="/auth/login"`,
    nomes `username`/`password` e `#erro-login`; link "Criar conta".
  - `GET /cadastro` + `POST /cadastro` (form) + `cadastro.html`; link "Entrar".
    Campos `Form()` com default `""` → validação no `ContaCreate` garante que
    vazio/comprimento inválido re-renderize o HTML (400), nunca 422 JSON.
- [x] **T3 — Chat**
  - Composer, Streaming Text (SSE), Thinking/Loading, Recommendation Card,
    Context Cards (fontes), Approval Card (aceitar/descartar), Tool Chips.
  - Preservar `hx-get="/chat/pergunta"`, `#conversa`, `sse-connect/sse-swap/sse-close`,
    `hx-post="/recomendacoes/{id}/feedback"` e a semântica de `textContent`.
  - Portado o primitivo **ChatComposer** (card, bolhas, composer com botão de envio)
    para `chat.html`/`chat_turno.html`; SSE validado no navegador.
- [ ] **T4 — Importar + Histórico**
  - Upload (card/dropzone), resultado (status card), histórico (Records/Filter table).
  - Preservar `name="tipo"`/`name="arquivo"` e textos assertados.
- [ ] **T5 — KPIs**
  - Insight Cards + período; preservar os 7 rótulos/valores e `name="desde"`/`"ate"`.
- [ ] **T6 — Admin (HTML)**
  - `/admin/usuarios`: tabela de usuários, alterar papel, remover;
    `exigir_papel("admin")`; endpoints form-encoded.

## Testes a atualizar (ver pesquisa)

- `tests/web/test_app.py` (`app.css`, SRI), `test_home.py` (attrs do login/hrefs),
  `test_chat_ui.py` (HTMX/SSE do chat), `test_chat_sse.py` (contrato SSE),
  `test_kpis.py` (rótulos/percentuais), `test_ingestion_ui.py` (nomes/textos),
  `test_feedback.py` (Aceitar/Descartar/Decisão), `tests/acceptance/test_f1_mvp.py`.
- Novos: `GET/POST /cadastro`, `/admin/usuarios`.

## Riscos

- `POST /onboarding` é JSON-only → o form de `/cadastro` usa handler próprio.
- Corrida de e-mail duplicado em `criar_conta` → tratar `IntegrityError` no handler
  do cadastro.
- Sem rate limiting (AD-015) → `/cadastro` público amplia superfície de spam
  (risco já documentado como adiado).
- CSS único de 191 linhas crescerá → dividir para respeitar o teto.
- Strings pt-BR assertadas literalmente pelos testes — não alterar textos visíveis
  sem atualizar os testes.
