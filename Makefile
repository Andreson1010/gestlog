.PHONY: install format lint test run check

## Dependências (uv gerencia o venv a partir do pyproject.toml)
install:
	uv sync --extra dev

## Qualidade
format:
	uv run black src/ tests/ alembic/
	uv run ruff check --fix src/ tests/ alembic/

lint:
	uv run ruff check src/ tests/ alembic/

test:
	uv run pytest

run:
	uv run gestlog

check: lint test
