# On-call Assistant

Read-only AI on-call agent. The project plan (Decisions, Phases, Progress tracker) lives outside this repo; each session takes the next step that isn't Done, on its own branch with one PR.

These are the instructions for every coding agent in this repo: Codex reads this file and `CLAUDE.md` imports it. Before working on a step, read [`factory/rules.md`](factory/rules.md). Words with a fixed meaning here are in [`GLOSSARY.md`](GLOSSARY.md).

## Commands

- `make install` — `uv sync --locked`
- `make check` — ruff lint + format check, pyright (strict), pytest, and the factory's `dotnet format` check and tests. Must pass before every commit.
- `make format` — auto-fix lint and formatting (Python and C#)
- `make schemas` — regenerate `schemas/` after changing a capability, `Diagnosis` or `Hypothesis` model; commit the result
- `make factory` — rebuild the factory tool after changing its code
- `bin/factory doctor` — check this machine for the factory (no model calls)
- `bin/factory ask --harness claude|codex "..."` — ask one harness one question, headless and without tools

## Rules

- The product is Python 3.13, `src/` layout, package `oncall`. Add dependencies with `uv add` (or `uv add --dev`), never by hand-editing the lockfile.
- pyright strict: every function, including tests, is fully annotated.
- The factory is C# on .NET 10 in `factory/` (tool in `factory/src/Factory`, xUnit tests in `factory/tests/Factory.Tests`). Warnings are errors and nullable checks are on. Small one-off jobs may be file-based C# scripts (`dotnet run job.cs`), but hooks call the compiled tool: a script takes about 1.6 s to start, the tool about 0.1 s.
- The agent zone must never hold secrets. Never commit keys, tokens or `.env` files.
- The product never imports `factory`, and nothing from `factory/` goes into product containers, `knowledge/` or the shopfront repo.
- Any decision that changes the plan gets an ADR in `docs/adr/` (numbered, short: Context / Decision / Consequences).
- Write in English.
