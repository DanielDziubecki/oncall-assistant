.PHONY: install lint format typecheck test check schemas

install:
	uv sync --locked

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

typecheck:
	uv run pyright

test:
	uv run pytest

check: lint typecheck test

schemas:
	uv run python -m oncall.contracts
