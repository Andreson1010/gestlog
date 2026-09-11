.PHONY: install format lint test run check

## Dependências (uv gerencia o venv a partir do pyproject.toml)
install:
	uv sync --extra dev

## Qualidade
format:
	uv run black src/ tests/
	uv run ruff check --fix src/ tests/

lint:
	uv run ruff check src/ tests/

test:
	uv run pytest

run:
	uv run gestlog

check: lint test
