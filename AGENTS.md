# On-call Assistant

Read-only AI on-call agent. The project plan (Decisions, Phases, Progress tracker) lives outside this repo; each session takes the next step that isn't Done, on its own branch with one PR.

These are the instructions for every coding agent in this repo, whichever harness runs it: Codex and Pi read this file, and `CLAUDE.md` imports it. Before working on a step, read [`factory/rules.md`](factory/rules.md). Words with a fixed meaning here are in [`GLOSSARY.md`](GLOSSARY.md).

## Commands

- `make install` — `uv sync --locked`
- `make check` — ruff lint + format check, pyright (strict), pytest. Must pass before every commit.
- `make format` — auto-fix lint and formatting
- `make schemas` — regenerate `schemas/` after changing a capability, `Diagnosis` or `Hypothesis` model; commit the result

## Rules

- Python 3.13, `src/` layout, package `oncall`. Add dependencies with `uv add` (or `uv add --dev`), never by hand-editing the lockfile.
- pyright strict: every function, including tests, is fully annotated.
- The agent zone must never hold secrets. Never commit keys, tokens or `.env` files.
- Nothing from `factory/` goes into product containers, `knowledge/` or the shopfront repo.
- Any decision that changes the plan gets an ADR in `docs/adr/` (numbered, short: Context / Decision / Consequences).
- Write in English.
