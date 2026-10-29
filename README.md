# On-call Assistant

[![ci](https://github.com/DanielDziubecki/oncall-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/DanielDziubecki/oncall-assistant/actions/workflows/ci.yml)

A vendor-agnostic, read-only AI agent that investigates production incidents like a senior on-call engineer.

> **Status:** early development (v0.1, step 1 of 26). The sections below describe the target design; most of it is not built yet.

## What it does

- **Onboards itself** onto an unfamiliar system. It reads the code and deployment config, asks a human only what the files can't prove, and produces a reviewable `system-profile.yaml` of services, dependencies and observability tools. Every finding cites a file and line.
- **Requests read-only access** through MCP servers or native API adapters, behind a credential proxy. The model never sees a secret.
- **Diagnoses incidents** when an alert fires. It returns a root cause backed by verifiable evidence (trace IDs, log lines, metric values, queue stats), a confidence level, and a proposed fix that a human must approve. Nothing is ever executed.

## How it's evaluated

On every PR, the agent runs against a catalog of incidents injected invisibly into a polyglot microservices system ([shopfront](https://github.com/DanielDziubecki/shopfront), a sanitized OpenTelemetry Demo fork) on two backend stacks: Prometheus / Loki / Tempo and Datadog. The evals measure:

- **Root-cause accuracy** against two simpler baselines (a rule-based ranker and a single LLM call without tools).
- **Evidence grounding**: how much of the cited evidence actually exists in the tool results, rather than being hallucinated.
- **False positives** on no-fault runs, and **calibration** of reported confidence.
- **Cost and time** per diagnosis.

## Design principles

- **Capabilities, not vendors.** The agent calls stable, typed capabilities (`search_logs`, `get_trace`, `query_metric`, …); vendors plug in behind them.
- **Read-only, enforced outside the model.** The backends' own key scopes and the credential proxy both refuse writes. Query cost, rate limits and redaction live in the proxy.
- **Append-only event log.** Every step of every run is recorded, so evidence can be verified and runs can be replayed.

## Development

Requires [uv](https://docs.astral.sh/uv/). Python 3.13 is installed by uv if missing.

```bash
make install     # uv sync --locked
make check       # ruff, pyright (strict), pytest
uv run oncall --version
```

Architecture decisions are recorded in [`docs/adr/`](docs/adr/).

## License

[MIT](LICENSE)
