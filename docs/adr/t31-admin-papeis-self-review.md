# ADR: t31-admin-papeis

## 1. Contexto & Objetivo

A T8 entregou o onboarding e o convite de usuários: a empresa nasce com um
fundador `admin` e pode vincular colegas com um papel (`admin`, `gestor` ou
`operador`). Só que, até aqui, um papel gravado era um papel permanente — não
havia como um administrador promover um operador, rebaixar alguém ou cortar o
acesso de quem saiu da empresa. A T31 fecha esse buraco e cumpre **ADM-01**:
*"Admin altera papel e remove usuários do tenant."* O ganho de produto é
direto: a gestão de pessoas deixa de depender de suporte/banco e passa a ser
autosserviço do administrador, com o critério de aceite *"mudança de papel
reflete permissões; remoção revoga acesso."*

O desafio arquitetural não foi o volume de código (três operações: listar,
alterar papel, remover vínculo), e sim não repetir erros de fronteira de
autorização. Toda rota de gestão mexe em *outra pessoa*, então três garantias
precisavam ser provadas, não presumidas: **só admin** pode gerenciar; um admin
nunca enxerga nem toca um usuário de **outra empresa**; e a empresa nunca fica
órfã de administrador. A essas somou-se um defeito latente de modelagem
(`GUID` vs. `Uuid`) descoberto no caminho e que precisou ser contornado sem
migration.

## 2. Decisões de Arquitetura

**1. Autorização por reúso do guard da T8, não por checagem nova**

As três rotas (`GET /empresa/usuarios`, `PATCH /empresa/usuarios/{usuario_id}`,
`DELETE /empresa/usuarios/{usuario_id}`) dependem de
`exigir_papel("admin")`, o mesmo guard criado na T8. Ele resolve o vínculo do
usuário autenticado via `get_current_membership` e responde 403 se o papel não
estiver na lista. Reutilizar esse guard em vez de reimplementar a checagem
mantém uma única fonte de verdade para "o que é ser admin" e garante que a
empresa usada nas operações é sempre `admin.empresa_id` — o tenant da sessão,
nunca um id vindo do corpo ou da URL. O endpoint admin-only usado pelos testes
para provar a mudança de permissão (`GET /admin`) consome o mesmo guard, então
"papel reflete permissão" é verificado pelo próprio mecanismo de autorização,
não por um mock paralelo.

**2. Isolamento por empresa resolvido na consulta: 404, não 403**

`_vinculo_do_usuario(session, empresa_id, user_id)` busca o vínculo filtrando
**simultaneamente** `Membership.empresa_id == empresa_id` e
`Membership.user_id == user_id`. Se o alvo existir, mas pertencer a outro
tenant, a consulta não devolve nada e a rota responde `404 "Usuário não
encontrado na empresa."` — deliberadamente o mesmo status de "não existe".
Diferir 403 (existe, mas é alheio) de 404 (não existe) transformaria o endpoint
em oráculo de enumeração de usuários de outros clientes. Além disso, o alvo
nunca é buscado por id global: o `empresa_id` da sessão entra na cláusula, o que
torna o vazamento impossível por construção, não por checagem posterior. A
listagem segue a mesma lógica: só vínculos da empresa da sessão.

**3. Remoção = apagar o vínculo, porque o acesso *é* o vínculo**

`remover_usuario` executa `session.delete(vinculo)` e responde 204. A revogação
não precisa de flag de inativo nem de logout forçado: `get_current_membership`
resolve a empresa a partir de `Membership` e levanta 403 quando não há vínculo.
Sem linha em `membership`, as dependências `get_current_empresa` e
`exigir_papel` deixam de ter base, e todas as rotas dependentes do vínculo caem
em "Usuário sem empresa vinculada." O teste de integração
`test_admin_remove_usuario_e_revoga_acesso` prova exatamente isso: antes da
remoção `GET /empresa` responde 200; depois, 403. Não apagamos o `User`, apenas
o vínculo com o tenant — a identidade sobrevive caso a pessoa seja reconvidada.

**4. Proteger o último administrador é regra de negócio, não de UI**

`_exigir_nao_ultimo_admin(session, vinculo)` centraliza a checagem: se o alvo é
`admin` e `_contar_admins(empresa_id) <= 1`, levanta
`UltimoAdministradorError`, que as rotas mapeiam para `409`. Tanto `alterar_papel`
(quando o novo papel não é `admin`) quanto `remover_usuario` chamam o mesmo
helper, de modo que a regra não pode ser esquecida numa das portas. A escolha do
409 é semântica: o pedido é válido, mas conflita com o estado atual do recurso —
não é falta de permissão (403) nem recurso ausente (404). O `PATCH` para o
mesmo papel (`admin` → `admin`) não dispara a guarda, pois `papel != "admin"` é
falso e não há rebaixamento real.

**5. Contornar o descasamento `GUID`/`Uuid` com `IN`, sem migration**

`Membership.user_id` é declarado como `Uuid` (SQLAlchemy) enquanto `User.id` é
`GUID` (tipo do FastAPI Users). No SQLite os dois serializam diferente — um como
hex de 32 caracteres sem hífen, outro com hífen — e um `JOIN` direto
`Membership ↔ User` retorna vazio. Em vez de alterar o schema (exigiria migration
fora do escopo da T31), `listar_usuarios` lê os vínculos da empresa e busca os
usuários com `User.id.in_(ids)`: o *bind* usa o tipo da coluna `User.id`, que é
exatamente o formato em que o usuário foi gravado, e o casamento funciona. O
comportamento está documentado no docstring da função e o débito da migration
fica registrado em "O que vem a seguir".

## 3. Concessões e Escolhas Práticas (Trade-offs)

- **Checagem de último admin é leitura-depois-escrita (TOCTOU):** duas
  requisições simultâneas de rebaixamento poderiam, em teoria, ambas passar por
  `_contar_admins` antes de uma commitar. No MVP o deploy é single-process com
  SQLite e o cenário exige dois admins agindo no mesmo instante; uma trava
  pessimista (`SELECT ... FOR UPDATE`) ou constraint no banco agregaria
  complexidade desproporcional ao valor. A janela fica documentada como
  limitação conhecida e deve ser reavaliada quando houver Postgres concorrente.
- **404 para alvo de outro tenant:** o suporte pode ter menos contexto do que um
  403 daria (o cliente não sabe se errou o id ou se não tem acesso). Preferiu-se
  não revelar existência de usuários de outros clientes — o custo de suporte é
  aceitável frente ao ganho de privacidade entre tenants.
- **Sem auditoria dos eventos de gestão nesta task:** mudanças de papel e
  remoções são atos administrativos que mereceriam trilha, e a T26 já entregou o
  catálogo (`EVENTO_*`, `registrar_evento`). Como `auth/accounts.py` opera sobre
  `AsyncSession` e a T26 registra via `Session` síncrona, integrar agora forçaria
  uma ponte entre as duas camadas de sessão (AD-013). O wiring fica para uma
  task dedicada, com o catálogo pronto para receber eventos como `papel_alterado`
  e `usuario_removido`.
- **Listagem sem paginação e sem resposta modelada:** `GET /empresa/usuarios`
  devolve uma lista de dicionários. No porte do MVP (poucos usuários por tenant)
  isso basta; uma resposta Pydantic e paginação só se justificam quando a
  listagem virar tela de grande volume.
- **`auth/accounts.py` como camada de acesso async:** o acesso a SQL em `auth/`
  contraria a regra geral "SQL só em `db/`/`repositories/`, mas é a exceção
  deliberada da AD-013 (FastAPI Users exige `AsyncSession`, e os repositórios
  seguem síncronos). A T31 seguiu o padrão já existente de `criar_conta`/
  `convidar_usuario`, em vez de criar uma ponte async→sync só para cumprir a
  regra ao pé da letra.

## 4. O que vem a seguir (Roadmap Imediato)

- **Migration de alinhamento `Membership.user_id` ↔ `User.id`:** unificar o tipo
  das duas colunas (idealmente `GUID` nas duas, ou ambas com o mesmo
  `TypeDecorator`) elimina o contorno por `IN`, permite `JOIN` e relacionamento
  ORM direto `Membership.user` e remove um risco residual silencioso — hoje um
  vínculo órfão (sem `User` correspondente) é descartado em silêncio pela
  listagem. Enquanto a migration não entra, `listar_usuarios` mantém o contrato.
- **Auditoria de gestão (catálogo da T26):** emitir evento por alteração de
  papel e remoção de usuário, com `empresa_id` e `user_id` do ator, fechando a
  rastreabilidade administrativa que SEC-02 pede para interações relevantes.
- **UI de administração (T33/HTMX):** os endpoints já são estáveis; a tela deve
  desabilitar o botão de rebaixar/remover quando o alvo for o último admin,
  antecipando o 409, e destacar o papel vigente para evitar cliques redundantes.
- **Suporte a múltiplas empresas por usuário:** a resolução atual usa o vínculo
  mais antigo (`_buscar_membership`), premissa de MVP. Quando a seleção de
  empresa ativa entrar, `exigir_papel` e as rotas de gestão precisarão receber o
  `empresa_id` selecionado, não o do vínculo mais antigo.

## 5. Validação de Qualidade e Segurança

- **Garantias de negócio e privacidade:** `Membership.empresa_id` da sessão entra
  em toda consulta de alvo, então um admin jamais lê ou altera usuário de outro
  tenant (teste `test_admin_nao_gerencia_usuario_de_outra_empresa` → 404 no
  `PATCH` e no `DELETE`). Operador recebe 403 nas três rotas
  (`test_operador_nao_gerencia_usuarios`). A mudança de papel reflete permissão
  pelo próprio guard (`test_admin_altera_papel_e_reflete_permissao`: op 403 na
  rota admin-only → 200 depois da promoção). A remoção revoga acesso
  (`test_admin_remove_usuario_e_revoga_acesso`: `GET /empresa` 200 → 403). O
  último admin é protegido no rebaixamento e na remoção
  (`test_protege_ultimo_administrador`: ambos 409). Nenhum id de tenant ou
  usuário vem do cliente; não há chamada a LLM nem envio de dado a provedor
  externo nesta task.
- **Cobertura e testes automatizados:** `tests/auth/test_admin.py` traz 7 testes
  de integração (listagem isolada por empresa, operador 403, mudança de papel
  refletindo permissão, remoção revogando acesso, alvo de outra empresa 404,
  alvo inexistente 404, proteção do último admin 409). Execução focada
  `tests/auth tests/web`: **57 passed**. Gate completo do projeto antes do
  review: **220 passed**, cobertura **98,18%** (gate de 80%).
- **Padrões de qualidade:** `uv run python -m black --check src/ tests/ evals/` →
  93 arquivos inalterados; `uv run python -m ruff check src/ tests/ evals/` →
  All checks passed. Docstrings e nomes em português, `from __future__ import
  annotations` presente, nenhum comentário fora de docstring, nenhum `print`,
  funções bem abaixo de 50 linhas e sem inversão da direção de dependência
  (`apps → agents → libs`, com a exceção documentada de `auth/`).

## Achados corrigidos no self-review

- **Guarda do último admin duplicada (baixa):** a mesma condição
  (`papel == "admin"` e `_contar_admins(...) <= 1`) estava copiada em
  `alterar_papel` e `remover_usuario`, com risco de divergirem numa manutenção
  futura. Extraída para `_exigir_nao_ultimo_admin(session, vinculo)`, chamada
  pelas duas operações; a regra passa a ter um único ponto de verdade.
- **Mensagem de `UltimoAdministradorError` pouco descritiva (baixa):** o erro
  carregava apenas o `user_id` cru. Como o valor não é exposto ao cliente (é
  mapeado para 409), o impacto era só de diagnóstico; o texto agora explicita
  "último administrador da empresa" junto do id.
- **Sem achados** de injeção, vazamento de segredo, quebra de tenancy, tipagem,
  formatação ou lint além dos acima. O descasamento `GUID`/`Uuid` não é
  regressão da T31: é débito pré-existente de modelagem, contornado com
  justificativa e registrado para migration futura.
