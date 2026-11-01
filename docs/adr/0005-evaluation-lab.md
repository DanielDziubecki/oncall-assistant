# 5. Evaluation lab: fault injection and leak check

Date: 2026-11-01 · Status: accepted

## Context

Step 4 builds the lab that injects incidents into shopfront and makes sure the agent can't tell an injected incident from a real one. The plan was written for the OpenTelemetry Demo fork, which needed a sanitizing collector and a relocated flag service to hide its built-in fault flags. Shopfront (ADR 4) has neither, so the lab only has to keep its own traces out of what the agent sees.

## Decision

**Layout.** The lab is its own package in this repo (`lab/`, a uv workspace member) with the `lab` CLI: `up`, `down`, `scenarios`, `inject`, `reset`, `status`, `leakcheck`. Its tests live in `tests/lab/`. It is never mounted into the agent or proxy zones.

**Scenario catalog.** There is one `lab/catalog/<opaque id>/scenario.yaml` per scenario: 10 incidents and 3 no-fault runs.
- The schema (`lab.scenario.Scenario`) reuses the agent's `FaultType`, `Component` and `EvidenceKind`, so ground truth and diagnoses are scored on the same terms.
- Ids are random (`inc_XXXX`) and each scenario has a canary token. Both exist only in the lab.
- Every fault scenario names the shopfront alert that starts it, and a test checks that each of those alerts exists in shopfront.

**Injection kinds.** Each kind has an undo.

| Kind | Mechanism | Undo |
| --- | --- | --- |
| `toxic` | Toxiproxy toxic (latency, reset_peer, ...) on a proxied link | `POST /reset` |
| `settings` | Redeploys a service with changed environment, through a generated compose override | Delete the override and recreate the service |
| `pause` | `docker pause` | `docker unpause` |
| `cpu_limit` | `docker update --cpus` | Recreate the container |
| `netem` | `tc qdisc ... netem` from a netshoot sidecar sharing the container's network namespace | `tc qdisc del` |
| `restart` | `docker restart` | Nothing to undo |

`lab reset` also clears toxics and unpauses containers left over from a crashed run. Only one scenario can be active at a time; the state lives in `lab/.state/`, which is gitignored.

**Invisible proxying.** A lab-only compose overlay (`lab/compose/overlay.lab.yml`) handles this:
- Toxiproxy joins the shared network under the alias `payment`.
- The real payment service moves to a private `lab-payment` network as `payment-real`.
- Checkout's config, traces and logs are unchanged.
- The collector joins the lab network (payment exports telemetry from there). A merged lab config keeps lab containers out of the `docker_stats` metrics.

This replaces the plan's sanitizing collector, which existed only to drop flag-evaluation events.

**Leak check** (`lab leakcheck`) scans two sources:
1. **The target repo at a git ref:** every text file, plus every commit message and patch in that ref's history (what a clone of the branch shows).
2. **Live telemetry:** Prometheus label names and values, Loki labels and the last 30 minutes of logs, Tempo tags and their values, and active alerts.

It looks for the denylist in `lab/leakcheck/denylist.yml` plus every scenario id and canary. One allowlisted line covers OpenTelemetry's `propagate.inject(` in fulfillment. CI runs the repo scan against shopfront `main` on every PR.

**Images.** Toxiproxy `ghcr.io/shopify/toxiproxy:2.12.0` and netshoot `nicolaka/netshoot:v0.14`.

## Consequences

- The step 4 *Runs* check, adapted:
  - shopfront `main` (files and history): 0 leaks;
  - the abandoned OpenTelemetry Demo branch `step-03-fork-stack-a`: 820 leaks (`flagd`, `openfeature`, `feature_flag`, ...);
  - live telemetry with the lab overlay running: 0 leaks.
- The structural part of the plan's leak check (Toxiproxy API, Docker socket and lab hosts unreachable from the agent and proxy zones) waits until those zones exist in step 6.
- Toxiproxy only proxies checkout → payment, which is all incidents 1 and 2 need. Another proxied link means one more entry in `toxiproxy.json` and the same network trick in the overlay.
- The old fork branch is still on GitHub. It isn't on shopfront's default branch, so a normal clone doesn't show it, but deleting it removes the risk entirely.
