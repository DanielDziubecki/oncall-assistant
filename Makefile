.PHONY: install lint format typecheck test check schemas lab-up lab-down leakcheck

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

# Evaluation lab. The target checkout defaults to ../shopfront (override with LAB_TARGET=...).
lab-up:
	uv run lab up

lab-down:
	uv run lab down

leakcheck:
	uv run lab leakcheck
