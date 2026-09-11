---
name: build-with-tests
description: How to build in this repo — match existing patterns, write tests alongside every function, run the project's gate checks before declaring done. Use whenever writing new code, fixing bugs, or extending existing modules. Triggers on any implementation task.
---

# Build With Tests

The rules that stop us from breaking things. Not a methodology — just the conventions that keep the suite green and the diffs reviewable.

## Discover before you write

Read `AGENTS.md` at the repo root first. It is the source of truth for the stack, the exact commands, and the project's conventions. Then find the existing pattern for the thing you're about to build:

- New module in an existing layer → read a sibling module in the same package and match its structure.
- New config value → add it to the project's single config module; never hardcode it inline.
- New data access → follow the existing repository/store pattern.
- New external integration → follow the existing client/adapter pattern.
- New constant → the config module is the single source of truth.

If you can't find an existing pattern, ask. Don't invent a new one silently.

## Code rules (non-negotiable)

Defaults for our Python repos — adapt to the project's language/stack where it differs:

- **Never mutate.** Return new objects and copies; never modify in place. Prefer immutable/frozen types.
- **Functions under 50 lines.** If it's longer, it's doing too much.
- **Nesting under 4 levels.** Flatten with early returns.
- **No hardcoded values.** Everything configurable lives in one config module.
- **No silent failures.** Every exception is caught and logged with context, or re-raised explicitly.
- **Validate at boundaries.** External input (network, files, user input) is validated on entry; internal calls don't need defensive checks.
- **`from __future__ import annotations`** on line 1 of every `.py` file.
- **`pathlib.Path`** always, never raw strings for paths.
- **`logger = logging.getLogger(__name__)`** — never `print()` (CLIs are the exception).
- **Lazy log formatting** — `%s` placeholders, never f-strings in log args.
- **Docstrings in the project's documentation language** on all public and private functions.
- **No comments outside docstrings**, unless the project explicitly allows them.

## Writing tests alongside code

Write the test before or immediately after the function — not at the end of the task.

### Test naming
`test_<description_of_what_it_tests>` — e.g. `test_parse_respects_sections`, `test_empty_query_returns_fixed_message`.

Both module-level `test_*` functions and `Test*` classes grouping related cases are acceptable. Match the surrounding files.

### What every test must cover
1. Happy path — normal input, expected output.
2. Empty/zero edge case — empty collection, empty string, zero results.
3. Failure path — what happens when something goes wrong.

### Never touch the network
External services (LLMs, HTTP APIs, databases, vector stores, message brokers) are **always mocked or faked** in the test suite. Inject the fake through a fixture (see `tests/conftest.py`); no test should require a live service or credentials.

## Gate checks — run before declaring done

The exact commands live in `AGENTS.md` / the `Makefile` — read them, don't guess. Typical shape for our Python repos:

```bash
# Full suite + coverage gate
uv run pytest

# Format
uv run black src/ tests/

# Lint
uv run ruff check src/ tests/
```

Coverage is a gate, not a suggestion. If it drops, write more tests — not fewer assertions.

```bash
# Faster feedback during development — bypass the coverage gate when focused
uv run pytest tests/path/to/test_file.py --no-cov -v
uv run pytest tests/path/to/test_file.py::test_name --no-cov -v
```

## What "done" means

- All gate checks pass.
- Coverage stays at or above the project's threshold.
- No hardcoded values introduced.
- No new patterns invented without documenting why.
- Every new function has at least: happy-path test, empty edge case, failure test.
- Formatter and linter pass.
