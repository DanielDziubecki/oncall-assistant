# Factory plan

The factory is the set of agents, checks and commands that help build this project. It
follows the MEGA course (season 4): keep one focused conversation, **Main**, and put
small, tested helpers around it wherever building the project hurts. The project plan
says *what* to build; this plan grows the factory beside it, one piece at a time, each
added when a project step needs it.

## How a factory piece is made

1. **Notice friction** while working on a project step.
2. **Write the expectations first**: Do / Expect / Never lines for what the helper must do. Daniel writes or approves them.
3. **Build it** through the `factory` command, on any harness.
4. **Prove it in the bench**: a separate tester drives an isolated workspace and judges only from what appears on screen. A helper never grades its own work.
5. **Bring it home** once the bench passes twice in a row. When it fails, change the helper, never the expectations.

## Principles

- **One writer.** Main owns the step and writes the code. Helpers read and return short findings.
- **Code gathers, the model judges.** Facts come from scripts with ids; a claim citing an id that isn't in the record is dropped.
- **Expectations are the ceiling.** New behavior adds expectations; nothing is loosened to pass.
- **Limits live in code.** Read-only flags, budgets and timeouts are set by the driver, not asked of the model.
- **People keep what can't be undone:** merges, money, accounts, and which version of a helper goes live.
- **Small first.** No helper while the whole project still fits in one conversation's context.

## Stages

| Stage | What | When | Course |
| --- | --- | --- | --- |
| **F0** Foundation | `AGENTS.md`, glossary, rules, ADR 5, capability map, VPS setup, `factory ask` and `factory doctor` | now | S01E04, S04E02 |
| **F1** Critic and bench | A helper beside Main that flags what a prompt leaves out, its side effects and steps that are too big; the bench that proves it | before step 4 | S04E01 |
| **F2** Context before work | A status widget (tracker, CI, PRs); a brief with a source on every line, gathered before each step; suggested memories | steps 5–11 | S04E02 |
| **F3** Domain agents | Experts for the proxy and security, the lab and leakage, the capability contract, and scoring: memories with receipts, glossaries, scenario checks in CI | steps 12–15 | S04E03 |
| **F4** Jobs that wake on events | A CI-failure reader that reports and never fixes; a nightly check | steps 9–19 | S04E04, S01E05 |
| **F5** Self-improvement | Sealed cases the editing agent can't read; a Trainer whose drafts go live only with two keys; asking the bench what to build next | steps 16–25 | S04E05 |

Stages after F1 are a forecast. If a different friction shows up first, we build for that instead.

## F0: Foundation (this PR)

- `AGENTS.md` for every harness; `CLAUDE.md` imports it.
- [`GLOSSARY.md`](../../GLOSSARY.md), [`factory/rules.md`](../../factory/rules.md), [ADR 5](../adr/0005-harness-neutral-factory.md).
- [`capabilities.md`](capabilities.md): what Claude Code, Codex, Herdr and tmux each offer the factory.
- [`vps-setup.md`](vps-setup.md): the VPS from scratch.
- `factory ask` (a C# tool on .NET 10, run as `bin/factory`): one question to one harness, headless and read-only, answer in one shape.
- `factory doctor`: tools, harness logins, memory and disk, without calling a model.

**Done when:**

- `make check` passes in CI.
- On the VPS, `bin/factory doctor` reports no failures.
- On the VPS, `bin/factory ask --harness claude "Reply with OK"` answers, and so does `--harness codex`.
- The events from that first real Codex run replace the synthetic test fixture.

## F1: Critic and bench (next)

- `factory agent <name>` opens a helper in a pane beside Main. Hooks pass it each prompt and reply as text: `UserPromptSubmit` and `Stop` exist in both harnesses. It numbers its findings and sends nothing to Main by itself. Sending one uses `hc send`, which waits until Daniel's half-typed draft is sent or cleared.
- `factory bench test <name>` runs Main and the helper in an isolated workspace with a copy of the repo that holds no agent files. A tester types the Do lines and judges the Expect and Never lines from quoted screen text only.
- The Critic's first job comes from the course and checks three things: does the prompt give enough information, does it name the side effects of the change, and should it be split.
- **Daniel writes** `factory/agents/critic/expectations.md`. F1 starts with a draft built from real requests in this project.
- **Done when** the Critic passes every expectation twice in a row in the bench, once with each harness as its worker.

## Keeping the two systems apart

- **Names.** `GLOSSARY.md` gives each side its own words: bench and lab, driver and adapter, factory agent and agent under test, job and run.
- **Fair comparison.** Factory config lives only in this repo. The benchmark's Claude Code runner starts with an empty config directory, in a clone of shopfront, so setups 1–3 get no context the other setups lack.
- **No leaks.** Factory memories may mention incident ground truth, so they never enter `knowledge/` (the corpus agents under test can search) or shopfront.
- **Separate money.** The factory runs on subscriptions; the product's API budget stays $40 a month.
