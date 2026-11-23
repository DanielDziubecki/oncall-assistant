# 8. Pi is the factory's harness

Date: 2026-11-23 · Status: accepted

## Context

ADR 5 left the harness to a trial on the VPS ([`vps-setup.md`](../factory/vps-setup.md), step 8): Pi with both subscriptions as providers, or Claude Code and Codex as two harnesses. The trial passes when Claude and ChatGPT both work from Pi, the course's extensions run, and Pi loads the repo's instructions once.

The trial ran on 2026-11-23 as `dev`, with Pi 1.6.0:

| Step | Result |
|---|---|
| Claude through the subscription | Works. `pi-claude-code` at commit `d5b5e04` lists 14 models under the `claude-code` provider. |
| ChatGPT through the subscription | Works. `/login`, then the ChatGPT (Codex) login, gives the `openai-codex` provider with 10 models. |
| One headless answer each | Both replied `OK`, exit 0, nothing on stderr: `claude-code/claude-haiku-5-5` and `openai-codex/gpt-6.2-sol`, with `--no-tools`. Samples in [`factory/samples/pi/`](../../factory/samples/pi/). |
| Course extensions | Installed (`herdr-pi-lab` at `83ad72f`, `herdr-pi-role` at `e51fca8`). `/lab doctor`: Pi, `hc` and `/agent` ready; `herdr-app not found on PATH`. Both need Pi inside the Herdr desktop app, which a headless VPS doesn't have. |
| Instructions load once | Pi's system prompt, read from its JSON output in this repo, holds `AGENTS.md` once and not `CLAUDE.md`: Pi takes one context file per folder. |

The code of all three extensions was read before installing. None has install scripts or runtime dependencies. `pi-claude-code` runs `claude -p` with Claude Code's tools off and relays its requests through a local server, on `127.0.0.1` only, to `api.anthropic.com`; it doesn't read Claude Code's credentials.

## Decision

- **Pi is the harness**, with the Claude and ChatGPT subscriptions as providers. Claude goes through `pi-claude-code`, ChatGPT through Pi's `openai-codex` login.
- **The course extensions count as working but untested here.** What failed is their need for the Herdr desktop app next to Pi, not Pi. They are tried for real when the factory runs Pi inside Herdr (F4).
- **Pi packages are pinned to a reviewed commit.** An unpinned git package is fetched and reset to its newest code every time Pi starts, so unreviewed code would run as `dev`.
- **Claude Code and Codex stay installed.** `pi-claude-code` needs the `claude` command, and both remain the fallback if a provider route stops working. The `factory-dotnet-drivers` branch is not needed now.

## Consequences

- The Claude route is experimental and depends on `claude -p` staying on the subscription (ADR 5). ChatGPT through Pi is the second provider that keeps the factory working if it doesn't.
- Pi runs tools without asking. Until the action monitor exists (F2, as a Pi extension), Pi runs only with `--no-tools` or while Daniel watches.
- `/lab test` and `/lab new` start more Pi agents with tools on, run a scenario's setup lines as shell commands, and link Pi's `auth.json` into a scratch profile. They wait for F2 as well.
- `CLAUDE.md` can keep importing `AGENTS.md`: Pi doesn't read it when `AGENTS.md` is in the same folder.
