---
name: write-fluid-hybrid-adr
description: How to document Architecture Decision Records (ADRs) in this repo — write rigorous, technical architectural records that seamlessly integrate business value and practical impacts into a single, fluid narrative. Ensures decisions are immediately clear to both engineers and cross-functional stakeholders (Product Managers, Tech Leads, Operations) without creating segregated technical vs. non-technical sections. Use whenever authoring, updating, or reviewing an ADR as part of a task or sprint delivery.
---

# Skill: write-fluid-hybrid-adr

## Descrição
Use esta skill sempre que for solicitado a criar, atualizar ou documentar um Registro de Decisão de Arquitetura (ADR). O objetivo é produzir um documento rigoroso e rastreável para a engenharia, mas que seja simultaneamente fluido, claro e transparente para partes interessadas não técnicas (Product Managers, Tech Leads, Negócios e Operações), sem dividir a explicação em blocos isolados do tipo "Versão Dev" vs. "Versão Leigo".

---

## Princípios Fundamentais de Redação

1. **Narrativa Fluida e Unificada:** Nunca crie caixas ou seções separadas de "Tradução para Negócios". Cada decisão deve ser um único texto contínuo onde o motivo do negócio e a implementação técnica coexistem organicamente.
2. **Contexto Antes do Mecanismo:** Explique *qual problema do mundo real ou de negócio precisava ser resolvido* antes ou junto com a introdução de métodos, classes, parâmetros ou estruturas de dados.
3. **Terminologia Técnica Contextualizada:** Identificadores exatos de código (funções, classes, variáveis, tipos) devem aparecer em notação de código (`exemplo`), mas sua utilidade prática deve ser evidente para quem lê a frase.
4. **Sem Jargões Desnecessários sem Analogia:** Termos como *seam*, *closure*, *dataclass*, *splat*, *dead-letter* ou *multitenancy* devem ser acompanhados de sua consequência prática imediata (ex.: *"isolamento estrito entre empresas para evitar vazamento de memória"*).
5. **Rastreabilidade e Rigor:** Manter métricas, decisões explícitas de escopo, arquivos alterados, testes automatizados e critérios de aceitação intactos.

---

## Template Estrutural da ADR

O agente deve seguir rigorosamente a estrutura abaixo:

```markdown
# ADR: [id-da-tarefa]-[nome-da-funcionalidade]

## 1. Contexto & Objetivo
[Descreva o estado anterior do sistema, o problema que motivou a mudança e a meta desta entrega. 
Explique em tom natural o que o usuário ou o produto ganha com isso e qual o desafio arquitetural 
central, sem jargões de código isolados.]

## 2. Decisões de Arquitetura

**1. [Título curto da decisão com foco no benefício/ação]**
[Explicação fluida contínua. Apresente a motivação de produto/segurança/manutenção e integre 
imediatamente os detalhes técnicos: nomes de classes, parâmetros, assinaturas e comportamentos. 
Mostre a justificativa técnica integrada ao impacto prático: por que essa escolha foi feita em vez de 
outra e como ela protege o sistema sem quebrar compatibilidade.]

**2. [Título da segunda decisão]**
[...]

## 3. Concessões e Escolhas Práticas (Trade-offs)
* **[Nome do ponto/compromisso]:** [Explique a decisão pragmática adotada nesta fase. Ex.: por que uma solução 
  simples foi escolhida agora, qual complexidade foi evitada e por que isso é seguro para o momento.]
* **[Segundo ponto]:** [...]

## 4. O que vem a seguir (Roadmap Imediato)
* **[ID da Próxima Tarefa] ([Nome/Foco]):** [Impacto claro na experiência ou na infraestrutura.]
* **[ID da Tarefa Seguinte] ([Nome/Foco]):** [...]

## 5. Validação de Qualidade e Segurança
* **Garantias de Negócio/Privacidade:** [Ex.: comprovação de isolamento de dados entre empresas, ausência de vazamento.]
* **Cobertura e Testes Automatizados:** [Nome dos testes principais, volume de testes aprovados e cobertura percentual.]
* **Padrões de Qualidade:** [Status de linters, tipagem estática e formatadores.]