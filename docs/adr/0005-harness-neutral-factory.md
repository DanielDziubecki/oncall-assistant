# 5. A harness-neutral development factory

Date: 2026-11-21 · Status: accepted

## Context

The project is built with coding agents, one step and one PR at a time. Building it is also how Daniel learns to build AI systems and workflows, following the MEGA course: one focused conversation, Main, with small helper agents around it, each tested before it is trusted. Daniel has Claude Code and Codex subscriptions and wants to use both as agents without depending on either vendor. Main runs on a 16 GB VPS, in the Herdr workspace.

## Decision

- **The factory is files and one small command in this repo.** `AGENTS.md` holds the instructions for every harness; Codex reads it and `CLAUDE.md` imports it with `@AGENTS.md`. Factory rules and model sizes live in `factory/`. The `factory` package, a uv workspace member, is the only code that starts a harness.
- **Harnesses are workers behind drivers.** A driver turns one job into one headless command (`claude -p`, `codex exec`) and reads the answer into one shape: text, model, time, tokens and cost. Jobs ask for a size, `small` or `large`, and `factory/models.toml` maps sizes to models per harness. Adding a harness means one driver and one table.
- **A factory job sees only its prompt.** Claude runs with `--safe-mode --tools ""`; Codex runs with `--sandbox read-only --disable hooks`. Neither loads the project's hooks, so the factory's own hooks can't trigger themselves.
- **Subscriptions build; API keys measure.** The factory runs on Daniel's subscriptions. The benchmark's Claude Code setups keep the metered API key held by the credential proxy, as the plan says: a subscription login can't sit behind the proxy, and its runs can't be priced or pinned the same way.
- **Workspace: Herdr, with tmux as a fallback.** The Herdr app runs on Daniel's computer and herdr-core (`hc`) on the VPS. Factory code drives terminals through `hc` (run, send, read, keys, wait), the same operations tmux offers.
- **One meaning per word.** `GLOSSARY.md` separates factory terms from product terms. The factory's black-box tester is the *bench*, because *lab* is the incident lab; a *driver* runs a harness, while an *adapter* talks to a backend.

## Consequences

- Harness features with different formats (subagents, MCP config) are generated from one source when the factory first needs them. Skills share one format and differ only in folder. [`docs/factory/capabilities.md`](../factory/capabilities.md) records what each harness supports.
- The Codex driver is tested against synthetic events until the first run on the VPS records real ones.
- Factory tests use fake harness executables and never call a model, so CI needs no model key.
- The factory's model use is separate from the product's $40/month LLM cap.
