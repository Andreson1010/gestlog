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
- [x] **T3 — Chat (redesign full-screen)**
  - Painel ocupa a altura da tela (`.chat`); **lista rolável** no topo e
    **composer fixo embaixo**; pergunta em bolha à direita e resposta do copiloto
    separada (rótulo + bloco próprio); auto-scroll.
  - Botão **Copiar conversa** (`data-copiar-conversa`) monta o texto da sessão
    (Você/Copiloto por turno) e copia via Clipboard API com fallback.
  - Preservar `hx-get="/chat/pergunta"`, `#conversa`, `sse-connect/sse-swap/sse-close`
    e a semântica de `textContent`.
  - **Limpeza**: saíram do chat o rótulo "Copiloto resposta", os marcadores
    "Resposta logística:"/"Justificativa:"/"Fontes:" (`texto_principal`) e os controles
    "Sem decisão/Aceitar/Descartar" (o endpoint de feedback continua, agora sem uso na
    tela). Justificativa/fontes seguem na `Recommendation` para relatórios futuros.
  - SSE validado no navegador (pergunta → resposta, rolagem, copiar).
- [x] **T4 — Importar + Histórico**
  - [x] Importar em **painel compacto** (largura de leitura), botão pill; hrefs/names preservados.
  - [x] **Dropzone primitivo** (`data-dropzone`): alvo clicável/arrastável com `input[type=file]`
    `sr-only` (mantém `name="arquivo"`), realce ao arrastar e nome do arquivo escolhido
    (`data-nome-arquivo`) via JS progressivo; sem JS o clique no alvo abre o seletor nativo.
  - [x] **Status card** dedicado no resultado (`status-ok`/`status-erro`) com ícone e textos
    assertados preservados ("N aceitas · M rejeitadas", "Linha X: motivo").
  - [x] Histórico: tabela em painel + chip de status.
- [x] **T5 — KPIs**: filtro (datas) e cards reestilizados no tema. **Removido do
      menu** a pedido (rota `/kpis` e KPI-01 preservados; acessível por URL).
- [x] **T7 — Shell + tema**: nav com **estado ativo** (aria-current), rodapé com
      usuário + **Sair** (`POST /auth/logout`) e **toggle claro/escuro** persistido
      em `localStorage` (`data-tema`), com script anti-FOUC no `<head>`.
- [x] **T6 — Admin (HTML)**
  - `/admin/usuarios`: tabela de usuários (e-mail + papel), alterar papel e remover,
    sob `exigir_papel("admin")`; endpoints form-encoded
    (`POST /admin/usuarios/{id}/papel`, `POST /admin/usuarios/{id}/remover`) que
    re-renderizam a página com erro (400 papel inválido / 409 último admin / 404
    outro tenant) ou redirecionam (303) ao sucesso.
  - Link **"Usuários"** na nav visível só para admin (`get_current_membership_optional`);
    a API JSON `/empresa/usuarios*` permanece inalterada.

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
