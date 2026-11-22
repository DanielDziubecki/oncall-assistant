.PHONY: install lint format typecheck test check schemas factory factory-check

install:
	uv sync --locked

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .
	dotnet format factory

typecheck:
	uv run pyright

test:
	uv run pytest

check: lint typecheck test factory-check

schemas:
	uv run python -m oncall.contracts

# The factory (C#, .NET 10): build the tool that bin/factory runs, or check it like CI does.
factory:
	dotnet build factory/src/Factory -c Release

factory-check:
	dotnet format factory --verify-no-changes
	dotnet test factory
