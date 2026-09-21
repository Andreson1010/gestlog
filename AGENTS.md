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
- **`src/gestlog/graph.py`** — `build_graph(model=None, settings=None,
  specialist_tools=None)`; injete `model` em testes e `specialist_tools` para
  trocar o mock pelas fábricas de tools do tenant (usado pelo Copilot Service).
  `run_query` é o helper de invocação (`recursion_limit`).
- **`src/gestlog/cli.py`** — REPL; `main` marcado `# pragma: no cover`.

### Estrutura e fronteiras

**Pacote único** (`src/gestlog/`), fatiado em três fronteiras conceituais. **Não é**
monorepo multi-pacote (ver AD-012 em `docs/specs/project/STATE.md`); a extração para
pacotes separados só se justifica quando houver deploy/escala independentes.

```
apps   (entrada / deploy)     cli.py, web/, auth/, copilot/
agents (grafo e domínio)      graph.py, state.py, agents/, tools/
libs   (fundação compartilh.) config.py, llm.py, db/, repositories/
```

Direção de dependência — **nunca invertida**:

```
apps  →  agents  →  libs
  └──────────────→  libs
```

Regra de bolso para escolher onde uma coisa nova mora:

- endpoint / página / autenticação → `apps` (`web/`, `auth/`, `copilot/`);
- nó / prompt / ferramenta / roteamento → `agents` (`agents/`, `tools/`, `graph.py`);
- modelo / repositório / config / integração base → `libs` (`db/`, `repositories/`, `config.py`).

`db/` + `repositories/` são a **única** porta de acesso ao banco; nada fora de `libs`
escreve SQL. `docs/` é conceitual e nunca é importado pelo código.

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
- Secrets: apenas em `.env`; referência em `.env.example`
- Limites de código: funções com até 50 linhas, aninhamento até 4 níveis e arquivos com até 800 linhas; acima disso, extrair/módularizar.

## Testes

- Organizados espelhando `src/`: nós de agente em `tests/agents/`, ferramentas em
  `tests/test_tools.py`, grafo em `tests/test_graph.py`.
- `tests/conftest.py` expõe `FakeChatModel` via fixture `fake_model_cls`: fila de rotas
  para o supervisor (`routes`) e fila de tool calls (`tool_calls`) para especialistas.
  **Nenhum teste deve tocar rede/Ollama.**
- `addopts` já liga `--cov=src --cov-fail-under=80`; por isso use `--no-cov` em execuções focadas.
- Alvos de tool call têm o formato
  `{"name": ..., "args": {...}, "id": "call-1", "type": "tool_call"}`.

## Loop de auto-melhoria (memória de erros)

Não espere o usuário pedir e não dependa de `/lesson`: ao **perceber que errou e
corrigiu**, grave a lição por conta própria antes de encerrar. Momentos que
disparam a gravação:

- gate (teste/lint/typecheck) que **falhou e depois passou** por um conserto seu;
- achado de **code review** (feature ou task) que você corrigiu;
- achado do **developer-self-reviewer** que você corrigiu;
- **dívida técnica** quitada que expôs um erro recorrente seu;
- **correção do usuário** sobre algo que você fez errado.

Procedimento:

- grave a lição em `.opencode/LESSONS.md` (único tier, deste projeto).
- Formato de cada entrada: `Gatilho / Erro / Regra / Evidência`; `id` sequencial
  `L-00N`; mais recente no topo; uma entrada por erro.
- Só registre lição nascida de erro **real, já corrigido e observado**. Nunca
  invente nem registre algo genérico/não verificado.
- Teto de ~40 linhas; o `/end` consolida (dedup + poda). `/lesson` é
  apenas override manual; o plugin `self-learning` injeta um lembrete no
  resultado do comando quando um gate vermelho fica verde.

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

### Fluxo da feature (épico + task)

Features grandes (ex.: F1, 34 tasks) usam uma **branch de integração** e um PR por
task — nunca uma branch longa com force-push.

- **Integração**: `feat/f1-mvp` acumula as tasks da F1. `main` só recebe a F1 no
  fim, via um PR de release (`feat/f1-mvp → main`) + tag (`v0.1.0`).
- **Task**: uma branch curta por task, cortada da integração, nomeada
  `feat/f1-tXX-<slug>` (ex.: `feat/f1-t10-home-auth`).
- **Self-review antes do review**: toda task, mesmo atômica, passa pelo subagente
  `developer-self-reviewer` (fase 5.5 do `feature-factory`), que corrige achados
  menores e gera a ADR `docs/adr/<slug>-self-review.md` — todo PR é revisado por
  pares, então a crítica própria vem antes.
- **PR**: um PR por task contra a branch de integração (não contra `main`), sempre
  com `tasks.md` e testes no mesmo PR. `main` nunca recebe push direto.
- **Gate antes do merge**: CI verde (`black --check`, `ruff check`, `pytest`) +
  self-review (com ADR) + code review com o skill **code-reviewer**. Squash-merge
  e apaga a branch.
- **Sem reescrever branch compartilhada**: nada de `force-push` em `main` ou na
  integração; corrigir com commits novos.

## Fluxo de Code Review

  Antes de abrir qualquer PR, executar code review com o skill **code-reviewer**.