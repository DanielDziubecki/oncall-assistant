# Rules for working on a step

Main follows these on every step of the project plan. Daniel owns this file; agents
suggest changes, they don't make them.

1. Take the first step in the tracker that isn't Done. One branch and one PR per step; a large step may span sessions.
2. Start with what you found, your plan and your questions. Change no files until Daniel answers.
3. Find the cause before changing anything. Reproduce a bug with a failing test first.
4. For every [L] step and the four learning pieces (minimal agent loop, LangGraph agent, evidence verifier, scorer), explain the design first. Daniel reviews it line by line or writes it himself.
5. A step is done when its *Runs* check works, `make check` passes in CI (from step 4 the leak check, from step 10 the eval gate), every decision has an ADR, any change to the plan is written back into the plan, and the tracker row is Done with the PR link.
6. Ask before anything outside the step's branch: merging, pushing to `main`, creating repos or issues, accounts, spending money, applying Terraform.
7. Never read, print or copy a secret. Subscription logins (`~/.claude`, `~/.codex`) and API keys never go into product containers or the agent zone.
8. Factory agents advise; only Main writes files. When two factory agents disagree, or a change forces a product decision, ask Daniel.
9. Factory memories and agent files never go into `knowledge/`, the event log or shopfront.
