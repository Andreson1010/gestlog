# AGENTS.md

Guia para agentes que trabalharem neste repositório. O sistema é um fluxo
multiagente em LangGraph para gestão logística.

## Stack

- Python >=3.11 | LangGraph + LangChain (langchain-core, langchain-openai)
- LLM via endpoint compatível com OpenAI (Ollama local por padrão)
- Config: `pydantic-settings` (`.env`)
- Qualidade: black (line-length 88), ruff (E/W/F/I/B/UP/C4/SIM), pytest + coverage

`pyproject.toml` é a fonte de verdade das dependências. `requirements*.txt` são
apenas espelho de conveniência; não edite um sem o outro.

## Comandos

```bash
uv sync --extra dev                 # cria/atualiza .venv a partir do pyproject
uv run pytest                        # suíte completa + gate de cobertura (80%)
uv run ruff check src/ tests/        # lint
uv run black src/ tests/             # formatação
uv run gestlog                       # REPL (requer Ollama acessível)

# Um único arquivo/teste — obrigatório --no-cov, senão o gate de 80% derruba
uv run pytest tests/agents/test_specialists.py --no-cov -v
uv run pytest tests/test_graph.py::test_graph_routes_to_specialist_and_finishes --no-cov -v
```

`make install|format|lint|test|run|check` encapsula os mesmos comandos.

## Arquitetura

Grafo supervisor + especialistas, com ciclo de retorno ao supervisor:

```
START -> supervisor --(state["next"])--> transporte | fornecedores | estoque
                        ^                          |
                        +--------------------------+
                       FINISH -> END
```

- **`src/gestlog/state.py`** — `AgentState` (`messages` com reducer `add_messages` +
  `next`) e os `Literal` `SpecialistName`/`Route`. Os nomes aqui são o contrato:
  precisam bater com os nós do grafo e com as chaves das arestas condicionais.
- **`src/gestlog/agents/supervisor.py`** — roteia via `with_structured_output(RouteDecision)`.
  Exige modelo com function calling / structured output.
- **`src/gestlog/agents/base.py`** — `create_specialist_node` executa um loop ReAct
  limitado por `max_tool_steps` e devolve **apenas a resposta final** ao estado pai
  (o histórico do supervisor não recebe `ToolMessage` intermediário).
- **`src/gestlog/agents/{transport,suppliers,inventory}.py`** — prompt + tools de cada especialista.
- **`src/gestlog/tools/*.py`** — ferramentas `@tool` com **dados mockados e determinísticos**
  (andaime até integração com TMS/ERP/WMS). Troque os corpos das funções, não a estrutura.
- **`src/gestlog/graph.py`** — `build_graph(model=None, settings=None)`; injete `model`
  em testes. `run_query` é o helper de invocação (`recursion_limit`).
- **`src/gestlog/cli.py`** — REPL; `main` marcado `# pragma: no cover`.

### Adicionar um especialista

Cinco pontos precisam mudar juntos:

1. `state.py`: adicionar ao `SpecialistName` e ao `Route`.
2. `agents/<novo>.py`: `PROMPT` + `build_<novo>_node`.
3. `agents/supervisor.py`: entrada em `SPECIALIST_DESCRIPTIONS`.
4. `agents/__init__.py`: reexportar o builder.
5. `graph.py`: incluir em `SPECIALISTS`, `add_node` e no mapa de `add_conditional_edges`.

Depois, cobrir o nó com `fake_model_cls` (ver Testes).

## Convenções

- Todo `.py` começa com `from __future__ import annotations`.
- Docstrings e prompts em português; código e nomes de funções/tools em português.
- Logging com `logger = logging.getLogger(__name__)`, nunca `print()` (a CLI é exceção).
- Não adicionar comentários fora dos docstrings.
- Todo agente/nó sem cobertura de teste deve ser testado com o modelo fake.

## Testes

- Organizados espelhando `src/`: nós de agente em `tests/agents/`, ferramentas em
  `tests/test_tools.py`, grafo em `tests/test_graph.py`.
- `tests/conftest.py` expõe `FakeChatModel` via fixture `fake_model_cls`: fila de rotas
  para o supervisor (`routes`) e fila de tool calls (`tool_calls`) para especialistas.
  **Nenhum teste deve tocar rede/Ollama.**
- `addopts` já liga `--cov=src --cov-fail-under=80`; por isso use `--no-cov` em execuções focadas.
- Alvos de tool call têm o formato
  `{"name": ..., "args": {...}, "id": "call-1", "type": "tool_call"}`.

## Gotchas

- Se um especialista nunca devolver `FINISH`, o loop volta ao supervisor até estourar
  `RECURSION_LIMIT` (`GraphRecursionError`). O supervisor é quem encerra.
- `SUPERVISOR_MODEL` vazio reaproveita `LLM_MODEL`; defina-o só se quiser um modelo
  separado para roteamento.
- `get_settings()` é memoizado com `lru_cache`; testes que mudam env precisam
  `get_settings.cache_clear()` ou instanciar `Settings(_env_file=None)` direto.
- `uv sync` pode selecionar um CPython mais novo que o local; o suporte é `>=3.11`.

## Git

- Branches: `feat/`, `fix/`, `refactor/`, `data/`.
- Commits em português, imperativo: `feat: adiciona especialista em estoque`.
