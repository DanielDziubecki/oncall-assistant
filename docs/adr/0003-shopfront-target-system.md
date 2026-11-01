# 3. Shopfront target system (step 3)

Date: 2026-11-01 · Status: superseded by [ADR 4](0004-shopfront-own-python-system.md)

## Context

Step 3 forks the OpenTelemetry Demo into `shopfront`, trims it, adds observability stack A (Prometheus, Loki, Tempo, Alertmanager, Grafana) and SLO alerts. Several details weren't settled by the plan, and a few turned out differently.

## Decision

- **Fork without upstream history.** Shopfront starts from a copy of the OpenTelemetry Demo **3.1.0** release, not a GitHub fork, so none of upstream's history (flag names, fault descriptions) is in the target's git history. Attribution is in `NOTICE` (Apache-2.0).
- **Upstream images for now, Docker Hub only.** Services run the published `otel/demo:3.1.0-*` images. Every image comes from Docker Hub, because it works in every environment used so far, including cloud sessions where GHCR downloads are blocked. The exception is flagd, which upstream publishes only to GHCR; step 4 moves it into the lab. Shopfront's own images get built once step 4 changes service code. The source in `src/` is upstream 3.1.0, unchanged.
- **12 application services, not about 10.** The plan said about 10. Kept: frontend, checkout, cart, product-catalog, recommendation, payment, shipping, quote, currency, email, ad and accounting, plus frontend-proxy, image-provider and load-generator. Removing `ad` or `email` needs code changes in frontend, load-generator and checkout, or leaves constant error logs. That can come with step 4's code changes if memory requires it. Removed: fraud-detection, flagd-ui, telemetry-docs, the AI agent services, Jaeger, OpenSearch, OpAMP and profiling.
- **20 simulated users instead of upstream's 5.** At 5 users checkout handles about 0.6 orders per minute, too few for an error-ratio alert to mean anything. At 20 it handles about 6 per minute. Browser (Playwright) users are off by default to save about 1 GB of memory.
- **Request metrics from the collector's span metrics connector**, flushed every 15 s. SLO alerts evaluate 2-minute rates every 15 s, and error-ratio alerts require a minimum request rate. Tempo's metrics generator adds service-graph metrics for `get_service_dependencies`. Container CPU, memory, throttling and restarts come from the collector's `docker_stats` receiver, and Kafka consumer lag from `kafkametrics`.
- **Twelve alerts** on symptoms, not causes: frontend, checkout, cart and shipping error ratios; frontend, checkout, cart and recommendation latency; product-catalog errors; `orders` consumer lag; frontend traffic surge; container restarts. Unit tests run with `promtool test rules`. The catalog's incidents map onto these alerts. An incident whose alert doesn't fire is marked invalid, as the plan says.
- **The collector config belongs to the stack** (`observability/stack-a/otelcol-config.yml`, selected with `OTEL_COLLECTOR_CONFIG`), so the Datadog variant can swap exporters without touching the application compose file.

## Consequences

- Until step 4 rebuilds `frontend-proxy`, its Envoy template still routes to UIs that no longer run. Those routes point at a closed local port.
- Running the whole stack on GitHub runners pulls from Docker Hub. The shopfront `stack` workflow measures memory and CPU on a runner on every PR (the step 3 *Runs* check).
- The alert thresholds are tuned to 20 users on a 4-vCPU machine. Incident scenarios that change load (traffic surge) depend on them.
