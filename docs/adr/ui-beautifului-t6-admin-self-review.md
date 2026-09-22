# ADR: ui-beautifului-t6

## 1. Contexto & Objetivo

Até aqui a gestão de usuários e papéis só existia como API JSON (`GET/PATCH/DELETE
/empresa/usuarios*`), pensada para consumo programático. Um administrador não
técnico dependia de ferramenta externa (curl, cliente de API) para trocar o papel
de alguém ou revogar um acesso — justamente a operação mais sensível do produto,
porque mexe em quem pode gerenciar a empresa. A T6 entrega a página **HTML
`/admin/usuarios`** sob o shell *beautifului*: lista a equipe (e-mail + papel),
permite alterar o papel e remover o vínculo, tudo restrito a administradores.

O desafio central não é desenhar a tabela, e sim **acrescentar uma superfície
privilegiada de escrita sem tocar no contrato JSON** e sem regredir as duas
garantias que sustentam o produto: o isolamento estrito entre empresas (um admin
nunca vê ou altera usuários de outro tenant) e a integridade da empresa (nunca
deixá-la sem administrador). A página é uma casca HTTP nova sobre casos de uso que
já existiam; a cobertura automatizada fecha em 8 testes de integração cobrindo
listagem, tenancy, authz, papéis inválidos e o guard do último admin.

## 2. Decisões Arquiteturais

- **Router HTML dedicado (`admin_ui.py`) separado do router JSON (`admin.py`), mas
  compartilhando os mesmos casos de uso de `gestlog.auth.accounts`.**
  - **Justificativa:** o contrato JSON `/empresa/usuarios*` permanece byte a byte
    inalterado (requisito do spec) e as regras de negócio — escopo por
    `empresa_id`, bloqueio do último administrador — ficam em um único lugar. A
    duplicação fica confinada à casca HTTP (formato do corpo, código de status,
    destino do redirect), que é exatamente onde HTML e JSON divergem de propósito.

- **Endpoints form-encoded com *POST/Redirect/GET* (303) no sucesso e re-renderização
  da própria página em erro, com status espelhando a API JSON: 400 (papel inválido),
  404 (vínculo inexistente/outro tenant) e 409 (último administrador).**
  - **Justificativa:** o navegador posta `application/x-www-form-urlencoded`, então
    um handler HTML dedicado é necessário para não devolver JSON cru ao usuário. O
    `303 → /admin/usuarios` evita reenvio do formulário ao recarregar. Manter os
    mesmos códigos da API (`400/404/409`) significa que a semântica de erro não
    diverge entre as duas portas, e o teste de contrato vale para ambas.

- **Escopo de tenancy sempre pelo `admin.empresa_id` da sessão e resposta `404` para
  vínculo de outra empresa, nunca `403`.**
  - **Justificativa:** `accounts.alterar_papel/remover_usuario` recebem
    `empresa_id` e só enxergam aquele tenant; um id de outra empresa simplesmente
    não é encontrado. Responder `404` em vez de `403` evita confirmar a existência
    do usuário em outro tenant (anti-enumeração), sem abrir mão do isolamento.

- **Gate de navegação por um novo `get_current_membership_optional` em `auth/deps.py`,
  exposto ao shell como a flag `admin`, consumida em `base.html` por `{% if admin %}`.**
  - **Justificativa:** o link "Usuários" deve aparecer *só* para admins, mas as
    páginas do shell (home, chat, importar, histórico, KPIs) continuam acessíveis a
    operador — então não se pode usar um guard `exigir_papel("admin")`, que
    derrubaria o operador. A dependência *opcional* devolve `None` quando não há
    sessão ou vínculo, permitindo que o template decida sem quebrar o fluxo de
    logout/usuário sem empresa. O router admin continua com o guard forte
    `exigir_papel("admin")` em todos os endpoints; o flag de nav é só apresentação.

- **Validação do papel do formulário derivada do mesmo `Literal` da API JSON
  (`get_args(Papel)`), e `Form()` com default `""`.**
  - **Justificativa:** fecha duas armadilhas já conhecidas: um campo `Form()`
    obrigatório recebendo valor vazio vira **422 JSON** em vez de cair no erro
    renderizado (L-009), e reescrever a lista de papéis localmente faria formulário
    e API divergirem em silêncio quando o domínio evoluísse (L-013). Opções do
    `<select>` e validação passam a ter uma fonte única.

- **Acessibilidade e consistência visual reaproveitando o design system existente.**
  - **Justificativa:** a tabela reusa `.painel-tabela`/`.tabela-historico` e os
    novos controles só consomem tokens (`--field`, `--line`, `--accent`,
    `--radius-control`), então claro/escuro funcionam sem regra extra. Cada
    `select` e botão recebe `aria-label` com o e-mail da linha, porque "Salvar" e
    "Remover" repetidos são ambíguos para leitores de tela.

## 3. Trade-offs & Compromissos

- **Página HTML em vez de reaproveitar a API JSON:** ganha-se usabilidade (um admin
  não técnico gerencia a equipe) ao custo de duas rotas para a mesma operação.
  Aceitável porque a lógica de negócio é compartilhada — o que se duplica é só a
  tradução de entrada/saída, e o contrato JSON permanece estável para integrações.

- **Sem token CSRF explícito nos formulários:** as ações mudam estado e são
  autenticadas por cookie. A mitigação vigente é o cookie `SameSite=Lax`, que faz o
  navegador não enviar o cookie em POST *cross-site*; o *hardening* de auth (rate
  limiting/CSRF) já está registrado como adiado no MVP (AD-015). É o mesmo padrão do
  `POST /auth/logout` existente, portanto não introduz superfície nova.

- **`get_current_membership_optional` adiciona um lookup de vínculo ao shell:** em
  páginas que também resolvem a empresa, pode haver consulta redundante de
  `Membership` por request (a dep de empresa não reaproveita a opcional). Aceitável
  no MVP — é uma leitura indexada, e a alternativa exigiria amarrar as dependências
  de auth umas às outras, arriscando mudar os status de 401/403 já cobertos.

- **Remover revoga o vínculo, não apaga o `User`:** preserva histórico e outros
  vínculos do mesmo usuário; o efeito prático é a perda de acesso (o usuário passa a
  cair em "sem empresa vinculada"). É a mesma semântica já praticada pela API JSON.

- **`AsyncSession` no `admin_ui`:** mantém a coerência com a camada de auth (AD-013),
  ainda que o resto do shell use sessão síncrona. A troca de um pelo outro seria um
  refactor maior que o escopo desta task.

## 4. Limitações Conhecidas

- Sem token CSRF explícito e sem confirmação no cliente antes de remover; a defesa
  atual é o `SameSite=Lax` do cookie (AD-015).
- `/admin/usuarios` sem sessão devolve **401**, não um redirect para `/login` como as
  demais páginas HTML, porque herda o guard compartilhado `exigir_papel`. O acesso
  indevido de um operador autenticado continua **403**.
- Um `usuario_id` malformado na URL devolve **422 JSON** do FastAPI, e não a página
  re-renderizada com erro.
- Sem rate limiting nas ações de administração (AD-015).
- Sem seleção de "empresa ativa" para usuários com múltiplos vínculos — o sistema
  segue usando o vínculo mais antigo de forma determinística.
