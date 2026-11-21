# Glossary

One meaning per word, for people and agents. The product and the factory share some
everyday words, so where they collide, each side gets its own term. Change a definition
only on purpose, in a PR, and say why.

## Product

| Term | Meaning | In code, or say instead |
| --- | --- | --- |
| Incident | A fault in shopfront that an agent must diagnose, such as "payment unreachable". | Not "chaos" or "test case". |
| Scenario | The file that defines one incident: its injection, the alert that marks it ready, and its ground truth. | `lab/catalog/<id>/scenario.yaml` |
| Catalog | All scenarios. | `lab/catalog/` |
| Injection | How the lab causes an incident: Toxiproxy, netem, a Docker action or a latent-bug setting. | |
| Latent-bug setting | A neutrally named shopfront setting that turns on a real bug in service code, off by default (ADR 4). | e.g. `PAYMENT_TOKEN_CACHE` |
| Ground truth | What a scenario expects as the root cause: a component, a fault type and a mechanism. | `ground_truth` |
| Component | A service (`payment`) or a link between two (`checkout->payment`). | `component` |
| Fault type | The kind of fault, from a closed list; `none` means there is no incident. | `fault_type` |
| Capability | A typed, read-only operation an agent calls, such as `search_logs`. Vendors plug in behind it. Served to agents as MCP tools. | `CAPABILITIES` |
| Adapter | Code that implements capabilities for one backend. | `adapters/`; not a factory *driver* |
| Backend | A system that stores telemetry. Stack A is Prometheus, Loki, Tempo and Alertmanager; stack B is Datadog. | |
| Ref | The id of one item in one tool result, `e<event_id>#<index>`, such as `e42#3`. | `Ref` |
| Evidence | One ref plus a quote or a value taken from that item. | `Evidence` |
| Grounded | Evidence whose quote or value is really in the tool result it cites. The evidence verifier checks this. | Not "true" or "correct". |
| Diagnosis | The answer every setup gives through `submit_diagnosis`: one to three root causes, each with a confidence and evidence. | `Diagnosis` |
| Setup | One agent configuration under test, such as "Claude Code with our MCP server and the on-call skill". | Not "agent" alone. |
| Agent under test | The agent inside a setup. It runs in the agent zone. | |
| Run | One setup on one incident, from injection to score. | Only for evals; factory work is a *job*. |
| Zones | The **lab zone** injects faults and scores runs, hidden from agents. The **proxy zone** is the only place secrets live. The **agent zone** holds no secrets and can reach nothing but the proxy. | |
| Lab | The product's control plane: injector, harness, scorer, leak check. | `lab/`; not the factory's *bench* |
| Leak check | Fails a run if anything an agent can see hints at the injection. | `lab leakcheck` |
| Canary | A random token placed only in lab files; finding it anywhere an agent can see is a leak. | `canary` |
| Tier | Where a scenario runs: `pr`, `nightly` or `release`. | `tier` |
| Snapshot | Recorded backend data for one incident window, replayed so PR evals need no live stack. | |
| Onboarding kit | Scans a team's repo, asks what files can't prove, and generates the system profile, MCP config, access requests and on-call skill. | `onboarding/` |
| On-call skill | The generated `SKILL.md` that setup 3 gives Claude Code. | Not a factory skill. |

## Factory

| Term | Meaning | In code, or say instead |
| --- | --- | --- |
| Factory | The agents, checks and commands that help build this project. Not part of the product. | `factory/` |
| Main | The one focused conversation that plans and writes the code for a step. Only Main edits files. | |
| Harness | A program that runs a model as a coding agent: Claude Code or Codex. | |
| Driver | Factory code that runs one harness headless and reads its answer. | `factory/src/factory/drivers/`; not a product *adapter* |
| Workspace | The program that hosts terminals and panes: Herdr, with tmux as a fallback. | `hc` is Herdr's command line. |
| Size | What a factory job asks for instead of a model: `small` or `large`. | `factory/models.toml` |
| Job | One piece of factory work, such as one `factory ask`. | Not "run". |
| Factory agent | A helper with one job, such as the Critic or a domain agent. It advises and never edits files. | `factory/agents/<name>/`; not an *agent under test* |
| Finding | One short, numbered item a factory agent reports. It reaches Main only when Daniel sends it. | |
| Expectations | Do / Expect / Never lines a factory agent must pass in the bench. Never loosened to make a report pass. | `expectations.md` |
| Bench | The factory's black-box tester (the course calls it "the lab"): it drives an isolated workspace and judges only from what appears on screen. | Not the *lab* |
| Memory | One dated rule a factory agent keeps, with a receipt: a commit, issue or PR. | Never stored in `knowledge/` |
