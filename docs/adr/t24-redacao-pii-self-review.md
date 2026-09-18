# ADR: t24-redacao-pii

## 1. Contexto & Objetivo

O copiloto manda a pergunta do operador para um LLM de terceiros, e a F1 nasce
com um compromisso explícito de LGPD (AD-005): PII de clientes — destinatários,
endereços de entrega e telefones de contato — não pode sair no prompt. Até aqui
nada no caminho tratava esse dado; a T25 é quem vai **ligar** a redação ao
copiloto, mas ela precisa de uma peça isolada e confiável para chamar. A T24
entrega exatamente isso: `redact(texto) -> RedactedText`, em
`src/gestlog/privacy/`, cumprindo o critério **SEC-01 AC1** (*"WHEN texto com PII
(nomes, endereços, telefones) vai ao LLM THEN o sistema SHALL redigir/minimizar a
PII antes do envio"*).

O desafio de projeto não é "encontrar PII" — é fazer isso **antes do LLM, sem
chamar o LLM**. Qualquer solução baseada no próprio modelo (pedir a um segundo
passe que reescreva o texto, ou usar um classificador de entidades treinado)
seria circular: o dado sensível teria que ser enviado ao provedor para ser
"protegido", anulando o objetivo. Além disso, o resultado precisa ser previsível
o suficiente para ser auditado e coberto por teste unitário. A pergunta de fundo
desta task, portanto, é: qual o mínimo determinístico de reconhecimento de PII que
já protege o caso de uso real da logística sem introduzir dependência de rede,
modelo ou serviço externo?

## 2. Decisões de Arquitetura

**1. Heurística regex + allowlist, sem LLM e sem dependência de rede**

`redacao.py` monta três famílias de reconhecimento: um padrão de **endereço**
(`_ENDERECO`, prefixo de logradouro + nome + número, com `nº`/`n` opcional), um de
**CEP** (`_CEP`) e um de **telefone** (`_TELEFONE`, com DDI/DDD e o nono dígito
opcionais). Nomes são casados por `_padrao_nomes`, que compila uma alternância a
partir da allowlist `NOMES_COMUNS` e ainda estende sobrenomes conectados
(`"João de Souza"`, `"Ana Paula"`). A justificativa de produto é direta: a
redação roda **no caminho crítico da pergunta**, então não pode adicionar latência
de rede nem custo por token; e, por ser uma função pura e determinística, o
mesmo texto sempre produz o mesmo resultado — o que torna a trilha de auditoria da
T26 verificável. O módulo só usa `re` e `unicodedata`, ambos da biblioteca padrão,
mantendo a fronteira `libs` intacta (nenhum import de `apps`/`agents`, nenhuma
chamada a `Settings` ou banco). A T25 pode, portanto, injetá-lo no copiloto sem
arrastar dependência para dentro do núcleo.

**2. Allowlist de prenomes em vez de NER: controle > cobertura**

A alternativa "de mercado" seria NER (*Named Entity Recognition*) com spaCy ou um
modelo de terceiros. Ela foi conscientemente rejeitada para o MVP. Primeiro,
porque NER exige baixar/empacotar um modelo de vários megabytes e, em alguns
casos, executá-lo em rede ou GPU — latência e superfície de dependência que um
reconhecimento por regex não tem. Segundo, porque um NER treinado em português
genérico erra justamente o que a logística tem de específico (nomes de
transportadoras, razões sociais), e a **correção do erro é assimétrica**: deixar
passar um nome é vazamento de PII (falha grave), redigir demais é desconforto
operacional (falha tolerável). A allowlist é auditável, versionável e testável
caso a caso; a política é injetável por tenant via a dataclass `PoliticaRedacao`
(`nomes`, `marcador_nome`, `marcador_endereco`, `marcador_telefone`), com
`POLITICA_PADRAO` como default — o gancho para um tenant acrescentar os nomes que
lhe importam sem tocar no núcleo.

**3. Determinismo explícito: cache, ordenação estável e substituição literal**

Duas medidas protegem a reprodutibilidade. A primeira é `_padrao_nomes` marcado
com `@cache`: o custo de montar a alternância é pago uma vez por allowlist, e
consultas repetidas reutilizam o mesmo `re.Pattern`. A segunda é a ordenação
`key=lambda nome: (-len(nome), nome)`, que além de evitar que um nome curto
"engula" um longo (por prefixo) garante ordem **estável** entre execuções — a
implementação anterior usava `key=len`, cujo desempate depende da iteração do
`frozenset`. E, para que o marcador de substituição nunca seja interpretado como
template de regex, a troca é feita com `marcador.replace("\\", r"\\")` antes do
`subn`: um marcador definido por um tenant com barra invertida agora vira literal
em vez de estourar `re.error` ou virar grupo de captura. É pouca coisa, mas é o
tipo de detalhe que separa "determinístico" de "determinístico na maioria dos
casos".

**4. `RedactedText` é o contrato do módulo e o texto original fica com o chamador**

A função devolve um dataclass `frozen` com o `texto` minimizado e a tupla
`categorias` (`"nome"`, `"endereco"`, `"telefone"`), mais a propriedade
`houve_redacao`. A decisão de **não devolver nem persistir o original** é
deliberada: a preocupação desta task é o que vai ao LLM, não o que a UI mostra. A
T25 preserva o texto original do lado de fora e envia apenas `resultado.texto` ao
provedor; a UI continua exibindo o que o operador digitou. Além disso, a tupla de
categorias — deduplicada na ordem em que as regras rodam — permite que a auditoria
da T26 registre "houve redação de telefone e nome" **sem** guardar o dado
sensível. As regras são aplicadas em ordem fixa (telefone → endereço → CEP →
nome), de modo que um número dentro de um endereço já é tratado pela regra certa e
o relatório de categorias é estável.

## 3. Concessões e Escolhas Práticas (Trade-offs)

* **Falsos positivos são o erro seguro — e "São Paulo" perde o "Paulo".** A
  allowlist contém `"Paulo"`, então a cidade **São Paulo** vira `São [NOME]`;
  nomes que também são cidades (`Vitória`) ou palavras (`vitoria`) sofrem o
  mesmo. Isso foi avaliado e **aceito**: no transporte, redigir demais um topônimo
  é reversível na cabeça do operador (ele reconhece o marcador), enquanto deixar um
  nome de pessoa passar é vazamento irreversível na LGPD. A assimetria justifica
  o viés. Se um tenant tiver um vocabulário de cidades que precise sobreviver, a
  `PoliticaRedacao` por tenant é o lugar de ajustar, sem mexer no default.
* **Nomes fora da allowlist não são redigidos.** `redact("O Zeca assume a rota")`
  passa intacto no default, porque `Zeca` não está em `NOMES_COMUNS` (há teste
  explícito para isso: `test_politica_padrao_nao_casa_nome_desconhecido`). É a
  limitação estrutural mais séria da abordagem: a proteção é proporcional ao
  tamanho e à curadoria da lista, não à capacidade de reconhecer qualquer nome.
  O caminho de evolução é a allowlist por tenant e/ou um NER local **como complemento**,
  nunca como único filtro — mas isso é decisão de outra iteração.
* **O reconhecimento de endereço exige número.** O padrão de endereço só fecha
  quando há um número ao final ("Rua das Flores, **123**"); logradouro sem número
  ou com "s/n" (`"Rua das Flores s/n"`), e abreviações sem ponto (`"Av Paulista
  1000"`), não são redigidos. A escolha evita redigir a palavra "rua" solta em
  frases comuns, ao custo de furar o caso sem número. Está registrado como
  limitação; a T25/T29 pode endurecer via policy.
* **Telefone e números de negócio colidem.** O padrão de telefone também casa
  sequências numéricas longas, como o final de uma chave de NF-e ou um número de
  pedido (`"Pedido 12345[TELEFONE]"`). Novamente, é o erro seguro para
  privacidade, mas polui números que não são PII. No MVP é aceitável; a evolução
  natural é exigir separadores/contexto ou uma allowlist de padrões de documento.
* **Sem alvo de tenant resolvido nesta task.** O design fala em "política por
  tenant", e o módulo entrega o **mecanismo** (dataclass injetável), não a
  **resolução** do tenant. Resolver qual empresa está logada e escolher a política
  é responsabilidade da T25, que já tem a sessão; manter a T24 sem banco é o que
  a deixa testável como unidade pura.

## 4. O que vem a seguir (Roadmap Imediato)

* **T25 (Integrar redação no copiloto):** chamada a `redact` sobre o texto do
  usuário antes de montar o prompt, guardando o original para a UI e o redigido
  para o LLM. O *Done when* é o teste que prova que o prompt não contém a PII de
  entrada — o consumidor direto do contrato `RedactedText`.
* **T26 (Auditoria e retenção):** a trilha por tenant pode gravar apenas as
  `categorias` de `RedactedText` ("houve redação de telefone"), sem persistir o
  dado sensível, fechando SEC-01 AC3.
* **T29/T32 (Golden set e KPIs):** a redação passa a incidir sobre as perguntas do
  conjunto de avaliação, medindo se a minimização não degradou a qualidade da
  recomendação; a limitação de nomes fora da allowlist é candidata a medição
  explícita nesse ponto.
* **Evolução da heurística:** endurecer endereço sem número, reduzir a colisão de
  telefone com números de negócio e estudar NER local como complemento da
  allowlist — cada item com teste e política por tenant antes de virar default.

## 5. Validação de Qualidade e Segurança

* **Garantias de negócio e privacidade:** `redact` é pura e não faz I/O — não
  chama o LLM, não acessa banco e não registra o texto original. Isso é a garantia
  central de SEC-01: o dado sensível só existe dentro do processo e só na forma
  minimizada é devolvido. O módulo vive na fronteira de fundação (`libs`), sem
  depender de `apps`/`agents`, e a política é injetável, então um tenant pode
  ajustar sua allowlist sem alterar o comportamento padrão de outro.
* **Cobertura e testes automatizados:** `tests/privacy/test_redacao.py` cobre
  texto sem PII intacto, texto vazio, cinco formatos de telefone, endereço com
  número, CEP, nome acentuado, nome com conector, nomes sem acentuação
  (regressão desta review), múltiplas categorias, política personalizada,
  marcador com barra invertida (regressão desta review) e imutabilidade de
  `RedactedText`. Execução focada: **17 passed**. Gate completo: **174 passed**,
  cobertura **97,83%** (gate de 80%).
* **Padrões de qualidade:** `uv run python -m black --check src/ tests/` → 78
  arquivos inalterados; `uv run python -m ruff check src/ tests/` → All checks
  passed. Docstrings e nomes de código em português (`redact`, `_padrao_nomes`,
  `_sem_acento`, `marcador_nome`), `from __future__ import annotations` presente,
  nenhum comentário fora de docstring, nenhum `print`, funções bem abaixo de 50
  linhas e aninhamento dentro do limite. Após a revisão, os `re.Pattern` de módulo
  ganharam anotação explícita (`re.Pattern[str]`) para alinhar com o tipo já
  declarado em `_padrao_nomes`.

## Achados corrigidos no self-review

* **Nome sem acentuação não era redigido (média-alta, SEC-01):** a allowlist
  guarda formas acentuadas (`"João"`, `"Antônio"`, `"Sérgio"`), mas o usuário
  digita com frequência sem acento — o próprio texto "sem PII" dos testes usa
  `"ate"`/`"distribuicao"`. Assim, `redact("Falar com Joao Silva")` passava
  **intacto**, um vazamento real do nome ao LLM. `_padrao_nomes` passou a incluir,
  para cada nome, também a forma `_sem_acento` (NFKD + remoção de diacríticos) na
  alternância; a forma acentuada continua valendo. Regressão coberta por
  `test_nome_sem_acentuacao_redigido`.
* **Marcador de política interpretado como template de regex (baixa, robustez):**
  `padrao.subn(marcador, ...)` tratava a string do marcador como sintaxe de
  substituição; um marcador por tenant com barra invertida (ex.: `r"\1"`)
  levantava `re.error` e derrubava a redação. A troca passou a escapar a barra
  invertida (`marcador.replace("\\", r"\\")`), tornando o marcador literal.
  Regressão coberta por `test_marcador_com_barra_invertida_e_literal`.
* **Ordenação de alternância não determinística (baixa):** `sorted(nomes,
  key=len, reverse=True)` deixava empates de comprimento na ordem de iteração do
  `frozenset`. Passou a `key=lambda nome: (-len(nome), nome)`, estável entre
  execuções, sustentando a tese de reprodutibilidade.
* **Polimento de tipagem (baixa):** `_ENDERECO`, `_CEP` e `_TELEFONE` ganharam
  anotação `re.Pattern[str]`, e a concatenação implícita da regex de telefone foi
  unificada.
* **Avaliado e apenas registrado (não bloqueante):** over-redação de cidades
  ("São Paulo" → `São [NOME]`), nomes fora da allowlist, endereço sem número/"s/n",
  abreviação sem ponto e colisão de telefone com números de negócio. Todos são o
  erro seguro para privacidade ou lacunas de cobertura documentadas na Seção 3;
  nenhum quebra um caso de SEC-01 coberto pelo *Done when*.
