# 5. A development factory modelled on a private AI lab

Date: 2026-11-22 · Status: accepted

## Context

The project is built with coding agents, one step and one PR at a time. Building it is also how Daniel learns to build AI systems and workflows, following the MEGA course. The course shows several ways to run such a "factory", from one conversation with small helpers (S04 build guides) to a coordinator delegating to workers (S01E04, S04E03a). The course author runs the most autonomous version as a private AI lab: one coordinator he talks to, workers in per-project sandboxes, secrets injected per project, an action monitor that checks every agent action, and approvals for anything critical. Daniel wants a setup like that.

Daniel has Claude Code and Codex subscriptions, a 16 GB VPS, and wants no dependency on one vendor. Two ways of using those subscriptions are open:

- **Claude Code and Codex** as two separate harnesses, with factory code in between. A first version of that code (C#, .NET 10) is kept on the `factory-dotnet-drivers` branch.
- **Pi** as the one harness, with Claude and OpenAI as providers inside it: Claude through the `pi-claude-code` extension, ChatGPT through Pi's own login.

## Decision

- **Direction: a private AI lab at the scale of one VPS.** Safety comes before autonomy: isolation, injected secrets and the action monitor exist before agents run unattended. The stages are in [`docs/factory/plan.md`](../factory/plan.md).
- **Workspace: Herdr.** The Herdr app runs on Daniel's computer and herdr-core (`hc`) on the VPS, so terminals keep running when the laptop is closed.
- **Harness: decided by a trial on the VPS.** The trial ([`vps-setup.md`](../factory/vps-setup.md), step 8) runs Pi with both subscriptions. If it works, Pi is the harness. If not, Claude Code and Codex stay, and the code on `factory-dotnet-drivers` is reused. A follow-up ADR records the result.
- **No factory code until the trial decides it.** This PR holds only what every option needs: `AGENTS.md`, the glossary, the rules, the capability map and the VPS guide.
- **Subscriptions build; API keys measure.** The factory runs on Daniel's subscriptions. The benchmark's Claude Code setups keep the metered API key held by the credential proxy, as the plan says: a subscription login can't sit behind the proxy, and its runs can't be priced or pinned the same way.
- **One meaning per word.** `GLOSSARY.md` separates factory terms from product terms. The factory's black-box tester is the *bench*, because *lab* is the incident lab.

## Consequences

- Headless use of a Claude subscription (`claude -p`, which `pi-claude-code` also relies on) may move to separate, smaller credits billed at API rates. Anthropic announced this in May 2026 and has put it on hold. No part of the factory may depend on that staying free of extra cost, and keeping a second vendor ready is part of the design.
- Until the trial, `CLAUDE.md` imports `AGENTS.md`. Pi reads `AGENTS.md` and `CLAUDE.md` from the working folder; the trial checks that it doesn't load the instructions twice.
- The factory's model use is separate from the product's $40/month LLM cap.
