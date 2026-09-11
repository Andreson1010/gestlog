# gestlog

Sistema multiagente de gestão logística baseado em [LangGraph](https://langchain-ai.github.io/langgraph/).

Um agente **supervisor** analisa a consulta e encaminha para um dos especialistas:

- **transporte** — fretes, prazos, rastreamento
- **fornecedores** — cadastro, avaliação, desempenho
- **estoque** — níveis, movimentações, reposição

Cada especialista usa ferramentas (`@tool`) com dados mockados, que servem de
andaime até a integração com os sistemas reais (TMS/ERP/WMS).

## Requisitos

- Python >= 3.11 e [uv](https://docs.astral.sh/uv/)
- Um LLM local compatível com OpenAI (ex.: [Ollama](https://ollama.com/)) com
  suporte a function calling / structured output

## Uso

```bash
uv sync --extra dev
cp .env.example .env      # ajuste LLM_MODEL / LLM_BASE_URL se necessário
uv run gestlog
```

Exemplo de sessão:

```
você> qual o frete de São Paulo para Curitiba com 10 kg?
gestlog> Frete São Paulo -> Curitiba | 10.0 kg | distância 408 km | R$ 1038.00
```

## Qualidade

```bash
uv run ruff check src/ tests/
uv run black src/ tests/
uv run pytest
```

Consulte `AGENTS.md` para a arquitetura do grafo e as convenções do projeto.
