# 2. Capability and diagnosis contracts

Date: 2026-10-29 · Status: accepted

## Context

The agent must never depend on a vendor. It calls capabilities (`search_logs`, `get_trace`, …) whose schemas stay stable while backends (Prometheus, Loki, Tempo, Datadog, MCP servers) plug in behind them. Its output, the `Diagnosis`, is scored by code and checked by the evidence verifier, so it must be precise enough to check mechanically.

## Decision

**Capabilities**
- Every input and output is a Pydantic model that is frozen and rejects unknown fields. The JSON Schemas are committed under `schemas/`, and a test fails if they are stale, so every contract change shows up in review.
- Every input takes an optional `time_range`. The proxy resolves it with `resolve_time_range`: missing means the last hour, anything longer than 24 h keeps its end and is cut to 24 h, and the end is never later than `now`. `now` is a parameter so evals can pin the clock to the incident time. For `get_trace` the range is only a lookup hint.
- `query_metric` takes a metric name, an aggregation enum, label filters and group-by labels. Names are validated with a pattern that accepts Prometheus and Datadog names and rejects any query expression, so the model can't write raw PromQL.
- Rates are ratios from 0 to 1 (`error_ratio`), not percentages. Durations are milliseconds and sizes are bytes, with the unit in the field name.
- `get_trace` returns a flat list of spans with `parent_span_id` rather than a nested tree. A flat list is easier to cite span by span and has no depth limit.

**Refs**
- Every output item has a `ref` of the form `e<event_id>#<index>`, e.g. `e42#3`. The ref is short so the model copies it reliably, and it can be checked with a regex.
- This commits the event log (step 7) to positive integer event ids, such as a Postgres `bigserial`. The caller allocates the event id before the call and the adapter fills in the refs.

**Diagnosis**
- 1 to 3 `root_causes`, ordered by confidence, so top-1 and top-3 accuracy come straight from the list.
- Each root cause is a `(component, fault_type)` pair plus a mechanism. A component is a service or a link (`checkout->payment`). `fault_type` is a closed enum; `none` means no incident and must not name a component.
- Confidence is a probability from 0 to 1 so the Brier score can be computed. The levels used for false-positive counting are derived from it: low below 0.4, medium below 0.7, high from 0.7.
- Every root cause other than `none` needs evidence. Each `Evidence` cites one `ref` and carries a `quote` (exact text such as a trace id or log substring) or a `value` (a number), so the verifier always has something to check.
- `unchecked` lists what the agent could not check, for the broken-tool robustness case.
- A `Hypothesis` that is `supported` or `rejected` needs evidence. An `open` one does not.

## Consequences

- Adding a fault type, capability or field is a visible schema diff plus a regenerated `schemas/` (`make schemas`).
- Adapters have to normalize units (ratios, ms, bytes) and generate refs.
- The integer event id format is fixed before the event log exists. Changing it later means changing the `Ref` pattern and the committed schemas.
