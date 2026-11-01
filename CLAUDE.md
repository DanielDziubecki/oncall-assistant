# On-call Assistant

Read-only AI on-call agent. The project plan (Decisions, Phases, Progress tracker) lives outside this repo; each session takes the next step that isn't Done, on its own branch with one PR.

## Commands

- `make install` — `uv sync --locked`
- `make check` — ruff lint + format check, pyright (strict), pytest. Must pass before every commit.
- `make format` — auto-fix lint and formatting
- `uv run lab ...` — evaluation lab (`up`, `scenarios`, `inject`, `reset`, `leakcheck`); needs a shopfront checkout at `../shopfront` or `LAB_TARGET`
- `make schemas` — regenerate `schemas/` after changing a capability, `Diagnosis` or `Hypothesis` model; commit the result

## Rules

- Python 3.13, `src/` layout, package `oncall`. Add dependencies with `uv add` (or `uv add --dev`), never by hand-editing the lockfile.
- pyright strict: every function, including tests, is fully annotated.
- The agent zone must never hold secrets. Never commit keys, tokens or `.env` files.
- Any decision that changes the plan gets an ADR in `docs/adr/` (numbered, short: Context / Decision / Consequences).
- Nothing from `lab/` (scenario ids, canaries, injection details) may ever reach the target repo or the agent. `lab leakcheck` enforces this; a new lab artifact that could leak needs a denylist entry in `lab/leakcheck/denylist.yml`.
- Write in English.
