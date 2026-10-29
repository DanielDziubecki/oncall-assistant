# 1. Python toolchain

Date: 2026-10-29 · Status: accepted

## Context

The project is a Python service with strict typing needs: capability schemas, the `Diagnosis` model and the event log are contracts that many components depend on. CI runs on every PR and must stay fast so the eval gate (step 10) fits in about 10 minutes.

## Decision

- **Python 3.13**, pinned in `.python-version`.
- **uv** for environments, dependency resolution and the lockfile (`uv.lock`, committed). CI installs with `uv sync --locked`, so an out-of-date lockfile fails the build.
- **uv_build** as the build backend, with a `src/` layout so tests run against the installed package, not the working directory.
- **ruff** for linting and formatting (one tool, replaces flake8, isort and black).
- **pyright in strict mode** over `src/` and `tests/`.
- **pytest** for tests, with `--strict-markers` and `--strict-config`.
- A **Makefile** as the single entry point (`make check`), used the same way locally and in CI.

## Consequences

- Strict pyright requires annotations on everything, including tests. Third-party libraries without type stubs will need stubs or targeted `# pyright: ignore[...]` comments with a reason.
- Contributors need uv installed; it installs Python itself.
