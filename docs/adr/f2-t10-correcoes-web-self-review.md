# ADR: f2-t10-correcoes-web

## 1. Contexto & Objetivo

O épico F2 (HITL) construiu, nas tasks anteriores, todo o motor de correções
cadastrais: o `ItemCorrecao` (T1), o `CorrectionRepository` escopado por empresa
(T2), as regras de completude (T3), as sugestões (T4), o `CorrectionService` que
materializa a fila (T5), a auditoria (T6), o fluxo de aprovação com aplicação (T7)
e o de rejeição (T8). Até aqui, porém, esse motor só era alcançável por código:
nenhum admin ou gestor conseguia **ver** a fila nem **decidir** pela interface.
A T10 fecha exatamente essa lacuna — transforma o domínio já testado numa tela
operacional. O critério de negócio é direto: uma pessoa com papel de aprovação
acessa `/correcoes`, revisa as sugestões agrupadas por tipo de cadastro, aprova
(quando há sugestão) ou rejeita (com justificativa), e a fila reflete a decisão na
próxima página. Quem não tem papel de aprovação não vê a tela nem no menu; quem
tenta decidir item de outra empresa recebe 404; sem sessão, 401.

O desafio arquitetural central não é desenhar a tabela — é conectar a camada web
`apps` ao serviço de domínio **sem duplicar regra de negócio e sem abrir brecha de
tenancy**. Toda a inteligência de "o que pode ser aprovado", "o que já foi
decidido" e "a qual empresa o item pertence" já vive no `CorrectionService` e
levanta exceções de domínio tipadas. A T10 precisa apenas **traduzir** essas
exceções para HTTP, delegar o escopo de empresa a quem já sabe resolvê-lo e
renderizar o resultado — nada de reimplementar validação no router.

## 2. Decisões de Arquitetura

**1. O tenant vem de `vinculo.empresa_id`, não de `get_current_empresa`**

A dependência `exigir_papel(*PAPEIS_APROVADORES)` já devolve o `Membership` da
sessão, e é o `Membership` que carrega `empresa_id`. O `CorrectionService` é
construído com esse id e recebe apenas `session` + `empresa_id`; toda leitura e
escrita do domínio parte daí. A alternativa natural — injetar
`get_current_empresa` — custaria uma consulta assíncrona adicional à tabela de
empresas só para extrair `empresa.id`, que é literalmente o mesmo UUID já presente
no vínculo. Evitar essa volta extra mantém o router linear, remove uma ida ao banco
por requisição e, sobretudo, elimina uma segunda fonte para o mesmo dado de
isolamento. Como o guard só libera quem tem papel de aprovação, o id que chega ao
serviço é sempre o da empresa do usuário autenticado; o teste
`test_fila_isola_outro_tenant` prova que um tenant não enxerga o item do outro, e
`test_decidir_item_de_outro_tenant_recebe_404` prova que a decisão cross-tenant
falha em vez de vazar.

**2. `PAPEIS_APROVADORES` é a fonte única do conjunto admin/gestor**

`("admin", "gestor")` foi declarado uma única vez em `gestlog.correcoes` e
reexportado. O guard da rota usa `exigir_papel(*PAPEIS_APROVADORES)`; o contexto de
todas as páginas que estendem `base.html` calcula `pode_aprovar` a partir da mesma
constante; e a entrada de navegação "Correções" só aparece sob `{% if pode_aprovar
%}`. A motivação é de manutenção e de segurança: se amanhã o produto decidir que
um novo papel também aprova, a mudança é um único ponto — guard e menu não podem
divergir. Antes desta revisão, a página de administração fixava `pode_aprovar:
True` diretamente; como o admin sempre pertence ao conjunto, o comportamento era
idêntico, mas o valor contornava a fonte única. A correção passou a derivar de
`admin.papel in PAPEIS_APROVADORES`, alinhando a página ao mesmo critério das
demais. O teste `test_operador_recebe_403` e o par
`test_nav_mostra_correcoes_para_gestor` / `test_nav_esconde_correcoes_para_operador`
travam os dois lados — acesso e visibilidade — para cada papel relevante.

**3. Erros de domínio são traduzidos para HTTP no router, com re-render PRG**

O router não valida estado de item: chama `servico.aprovar`/`servico.rejeitar` e
mapeia as exceções tipadas que o serviço já documenta. Item fora do tenant vira
`CorrecaoNaoEncontrada` → **404**; item terminal ou sem sugestão vira
`CorrecaoNaoAprovavel` → **409**; alvo ausente/alterado vira `CorrecaoAlvoInvalido`
→ **409** (o item já foi encerrado como `falhou` pelo serviço); rejeição sem
justificativa vira `JustificativaObrigatoria` → **422**; e uma decisão que não seja
`aprovar`/`rejeitar` é recusada antes de chegar ao serviço → **422**. Em todos esses
casos a resposta é a **própria página de correções re-renderizada** com um aviso
(`role="alert"`), não um JSON de erro: o operador continua na tela, com a fila
atualizada e a mensagem legível. No caminho feliz, a resposta é
`RedirectResponse` **303** para `/correcoes` (Post/Redirect/Get), o que impede que
um F5 reenvie a decisão. Esse desenho mantém a regra no domínio (os testes de T7/T8
já a cobrem) e deixa ao `apps` apenas a responsabilidade de apresentação.

**4. Paginação por `limite`, validado por `Query(ge=1, le=500)`**

`GET /correcoes` aceita `limite` com default 200 e teto 500, declarado como
`Annotated[int, Query(ge=1, le=_LIMITE_MAXIMO)]`. Valores fora da faixa são
recusados pelo próprio FastAPI com **422**, sem código de validação manual; os
limites vivem em constantes de módulo (`_LIMITE_PADRAO`, `_LIMITE_MAXIMO`), não
espalhados na assinatura. O mesmo parâmetro é aceito no `POST` para que o
re-render de erro reponha exatamente a mesma janela que o usuário estava vendo —
sem isso, um erro numa página "limitada" o devolveria à visão completa, perdendo o
contexto. O teste `test_limite_invalido_recebe_422` cobre os extremos e
`test_limite_restringe_listagem` prova que o teto de fato corta a listagem (3
itens com `limite=3`, 1 com `limite=1`). Optou-se por limite/cap em vez de
`offset`/página numerada porque a fila operacional do MVP é curta e o objetivo é
proteger a renderização de um volume anômalo, não navegar em arquivo.

**5. Estado vazio distingue "sem dados importados" de "fila vazia"**

Quando não há pendentes, a página não mostra a mesma mensagem para situações
diferentes. `_tem_dados` verifica se a empresa tem ao menos um registro nos três
catálogos (`StockRepository`, `SupplierRepository`, `TransportRepository`): se
**não** tem, o vazio é "**Sem dados importados**" com um link para `/importar`,
porque não há cadastro algum para completar; se **tem** dados mas a fila está
vazia, é "**Nenhuma correção pendente**", porque os cadastros já estão completos.
A distinção tem valor operacional real — evita mandar o usuário "importar" quando
ele já importou, e evita sugerir "está tudo certo" quando o problema é ausência de
dados. Os testes `test_fila_sem_dados_orienta_importar` e
`test_fila_vazia_com_cadastros_completos` fixam os dois ramos.

**6. A materialização da fila é idempotente e acontece no GET**

`GET /correcoes` chama `servico.gerar_fila()` antes de listar. Isso materializa os
itens pendentes a partir do estado atual dos cadastros e, em seguida, lista os
`pendente`. A operação de geração é idempotente por construção
(`abertos_para`/`existe_para` impedem recriar item aberto ou já decidido com o
mesmo valor), então um GET repetido não duplica itens — o teste
`test_aprovar_redireciona_aplica_e_sai_da_fila` aprova, volta a carregar a fila e
confirma que ela fica vazia em vez de regenerar o que acabou de sair. Assumir o
`commit` no GET é deliberado: a fila deve refletir o cadastro no instante da
consulta, sem exigir um passo assíncrono de geração separado.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **`GET` com efeito de escrita.** Gerar a fila no `GET` faz uma requisição de
  leitura commitar itens novos. É seguro porque a geração é idempotente e escopada
  ao tenant, e é o que entrega a experiência "abri a tela e a fila está atualizada".
  A alternativa — um job separado — adicionaria latência e um estado intermediário
  que o MVP não precisa.
* **`limite` em vez de paginação navegável.** Não há "próxima página" nem total de
  páginas; há um teto configurável por link. Cobre o caso de proteger a tela de um
  volume grande e é reversível quando a fila crescer.
* **`_tem_dados` percorre os três catálogos.** Em cada render vazio a página faz
  três listagens completas só para decidir a mensagem. É aceitável no MVP (dados
  mockados/pequenos) e o custo só é pago quando a fila está vazia.
* **`CorrecaoFalhaEscrita` não é re-renderizada.** Uma falha inesperada de escrita
  durante a aprovação (o serviço já faz rollback e marca o item como `falhou`)
  propaga como erro interno (500) em vez de página amigável. O escopo da T10 lista
  apenas 403/404/409/422; tratar 500 como página fica para uma iteração futura.
* **Sem token CSRF.** O fluxo usa cookie de sessão e segue o mesmo padrão das
  demais rotas `POST` já existentes no projeto; um token CSRF é uma decisão
  transversal a todas as telas, não específica da T10.
* **`Form()` com default `""` (L-009).** `decisao` e `justificativa` são
  declarados como `Annotated[str, Form()] = ""` para que a ausência do campo
  re-renderize a página com 422 em vez de estourar um 422 JSON de validação do
  framework — a mesma lição já aplicada nas telas anteriores.

## 4. O que vem a seguir (Roadmap Imediato)

* **T11 (Web — trilha de ações, P2):** `GET /correcoes/historico` com filtro
  `desde`/`ate`, reaproveitando `CorrectionRepository.listar_trilha` e o padrão de
  datas de `web/kpis.py`, para dar visibilidade ao que foi decidido.
* **T12 (Aceitação F2 + ajustes):** arquivo de aceitação ponta a ponta cobrindo os
  critérios INC/SUG/APR/ESC/TRA/EDG com dois tenants e modelo fake, mais ajuste das
  suítes existentes.
* **Tratamento de 500 amigável:** página de erro para `CorrecaoFalhaEscrita`, se o
  produto quiser o operador de volta à fila mesmo numa falha de escrita.
* **CSRF nas rotas de decisão:** se o projeto adotar proteção CSRF, esta rota entra
  junto com as demais ações `POST` de uma vez.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio e privacidade:** a fila só lista itens do
  `vinculo.empresa_id` da sessão (`test_fila_isola_outro_tenant`), decisão
  cross-tenant devolve 404 (`test_decidir_item_de_outro_tenant_recebe_404`) e
  `operador` é barrado no guard e no menu (`test_operador_recebe_403`,
  `test_nav_esconde_correcoes_para_operador`). Sem sessão, `get_current_user`
  responde 401 (`test_sem_sessao_recebe_401`). Nenhum teste toca rede/Ollama.
* **Cobertura e testes automatizados:** `tests/web/test_correcoes.py` com **18
  casos**, cobrindo acesso por papel, estados vazios, limite, decisão inválida,
  404/409/422, PRG/aplicação e navegação. `src/gestlog/web/correcoes.py` em
  **100%** de cobertura. Gate completo: **384 passed**, cobertura total **99,05%**
  (acima do mínimo de 80%).
* **Padrões de qualidade:** `uv run black --check src/ tests/` → 114 arquivos
  inalterados; `uv run ruff check src/ tests/` → All checks passed.
  `from __future__ import annotations` presente, docstrings e nomes em português,
  sem comentários fora de docstring, sem `print`, funções abaixo de 50 linhas,
  aninhamento abaixo de 4 níveis e sem SQL em `web/` (a persistência continua
  confinada a `db/` + `repositories/`).

## Achados corrigidos no self-review

* **`admin_ui.py` fixava `pode_aprovar: True` contornando a fonte única
  (baixo):** o valor era sempre verdadeiro porque a rota exige `admin`, então não
  havia impacto observável no menu, mas o contexto ignorava `PAPEIS_APROVADORES` e
  divergiria do critério usado nas demais páginas se o conjunto mudasse. Passou a
  derivar de `admin.papel in PAPEIS_APROVADORES`, com o import correspondente.
* **Linha em branco dupla no CSS de correções (trivial):** o bloco `.fonte`
  deixava dois espaços em branco antes do `@media`; reduzido a um, alinhando ao
  restante do arquivo.
* **Sem demais achados** de lógica, tenancy, fronteiras de camada, tratamento de
  erro, tipos ou imports; nenhuma correção mudou comportamento coberto por teste
  (18 + 9 testes de web verdes após as alterações).
