# Factory plan

The factory is the set of agents, checks and workflows that help build this project. Its
model is the course author's private AI lab: Daniel sets goals and gives final approvals;
a coordinator and its workers do the work in sandboxes; secrets are injected per project;
an action monitor checks what agents do. Here it is scaled to one 16 GB VPS (see ADR 5).

The project plan says *what* to build. This plan grows the system that builds it.

## Principles

- **Safety before autonomy.** Isolation, injected secrets and the action monitor exist before any agent runs unattended.
- **People keep what can't be undone:** critical merges (until F6, every merge: ADR 7), money, accounts, secrets, and which version of an agent goes live.
- **One writer per task.** One agent edits a task's files; others read and report.
- **Code gathers, the model judges.** Facts come from scripts with ids; a claim citing an id that isn't in the record is dropped.
- **Limits live outside the model.** Sandboxes, flags, budgets and the action monitor enforce what instructions only ask for.
- **Expectations are the ceiling.** Every agent has written expectations and is proven by a check it can't read. When it fails, the agent changes, never the expectations.
- **Small first.** Each stage starts with the smallest thing that works on this project.

## Stages

| Stage | What | Lab part | Course |
| --- | --- | --- | --- |
| **F0** Foundation (this PR) | `AGENTS.md`, glossary, rules, capability map, VPS guide, and the Pi trial that picks the harness | — | S01E04, S04E02 |
| **F1** Secure base | VPS reachable only through Tailscale; an isolated container per project for agent work; secrets injected per project, never on disk (Bitwarden Secrets Manager: one machine account per project); outbound-only networking for agents | Private network, sandboxes, password vault | S01E05, S04E02a |
| **F2** Action monitor | A hook before every tool call (`PreToolUse` exists in Claude Code and Codex; Pi uses an extension) asks a small model to allow, deny or ask Daniel; every decision is logged; proven against a set of dangerous and harmless commands | Action monitor | S02E05, S04E04 |
| **F3** Reach Daniel anywhere | Approvals and notifications on Daniel's iPhone (ntfy, or similar), including whether a PR needs his attention; the coordinator reachable from the phone | "ask approval" | S01E05 |
| **F4** The coordinator | One coordinator Daniel talks to. It starts workers as Herdr templates, each in its own git worktree inside the project sandbox. Work is shared through files: one folder per task with notes and evidence, claimed by one agent at a time. First job: run project steps and open PRs for approval. | AI agents | S01E04, S04E03a |
| **F5** Knowledge base | A Markdown repo of decisions, repo maps and run logs; relevant parts are pushed to workers; a librarian agent keeps it tidy | Knowledge base | S01E03, S04E02 |
| **F6** Quality layer | The Critic, the bench, domain agents with memories and scenario checks, sealed cases, and a Trainer behind two keys. A reviewer says whether each PR needs Daniel, and agents merge what isn't critical (ADR 7). The less Daniel watches, the more these must catch. | (checks) | S04E01–S04E05 |

Later stages are a forecast and will change with what we learn.

## F0: Foundation (this PR)

- [`AGENTS.md`](../../AGENTS.md) for every harness; `CLAUDE.md` imports it.
- [`GLOSSARY.md`](../../GLOSSARY.md), [`factory/rules.md`](../../factory/rules.md), [ADR 5](../adr/0005-harness-neutral-factory.md).
- [`capabilities.md`](capabilities.md): what Pi, Claude Code, Codex, Herdr and tmux offer.
- [`vps-setup.md`](vps-setup.md): the VPS from scratch, ending with the Pi trial.

**Done when:**

- The VPS is set up and both subscriptions answer a headless question.
- The Pi trial is done and its result is written down as ADR 8: Pi as the harness, or Claude Code and Codex (reusing the `factory-dotnet-drivers` branch). Done: [ADR 8](../adr/0008-pi-as-harness.md) picks Pi.

## Keeping the factory and the product apart

- **Names.** `GLOSSARY.md` gives each side its own words: bench and lab, factory agent and agent under test, job and run.
- **Fair comparison.** Factory config lives only in this repo. The benchmark's Claude Code runner starts with an empty config directory, in a clone of shopfront, so setups 1–3 get no context the other setups lack.
- **No leaks.** Factory memories may mention incident ground truth, so they never enter `knowledge/` (the corpus agents under test can search) or shopfront.
- **Separate money.** The factory runs on subscriptions; the product's API budget stays $40 a month.
