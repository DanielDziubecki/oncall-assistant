# 4. Shopfront as our own Python system

Date: 2026-11-01 · Status: accepted · Supersedes [ADR 3](0003-shopfront-target-system.md)

## Context

ADR 3 built shopfront as a trimmed fork of the OpenTelemetry Demo. That fork was rejected before merge, for two reasons:

- The project should run on a system its author knows and wrote, not on someone else's demo.
- A public demo is likely in the model's training data, together with its fault flags and their descriptions.

## Decision

Shopfront is our own system, all Python.

- **Services:** storefront, catalog, cart, checkout, payment, shipping, recommendation and fulfillment.
  - All are FastAPI apps except fulfillment, which is an asyncio Kafka consumer.
  - They live in one uv workspace and build from a single Dockerfile.
  - `libs/shopkit` holds the shared OpenTelemetry setup, JSON logging, the app factory and HTTP clients.
- **Infrastructure:** PostgreSQL (`catalog`, `shipping` and `orders` databases), Valkey and a single-node Kafka (KRaft, no ZooKeeper). A Locust load generator runs 20 shoppers.
- **Kafka is the only broker.** RabbitMQ was built first and then replaced. Kafka is more common in production systems, consumer lag is the standard backlog signal, and reading a dead-letter topic doesn't consume it, which suits a read-only `peek_dead_letters`. The cost is about 220 MB more memory than RabbitMQ.
  - checkout publishes to `orders` (3 partitions, keyed by user, `acks=all`, idempotent producer).
  - fulfillment consumes it as group `fulfillment` and commits offsets only after an order is stored.
  - Malformed messages go to `orders.dlq`, with the reason, the source offset and the trace context in the message headers.
  - A one-shot `kafka-init` container creates both topics; automatic topic creation is off.
  - The v0.2 queue incidents (poison message, dead-letter build-up, slow consumer, dropped broker connection) move to Kafka.
- **Plain HTTP/JSON between services** (httpx), with no gRPC.
- **Latent bugs live in the service code**, behind neutrally named settings in `.env` that are off by default. Step 4's lab turns them on; nothing has to be sanitized.
- **Observability stack A, the alert approach, the smoke test and CI** carry over from ADR 3. The alerts are renamed for the new services. `OrdersBacklogHigh` uses the fulfillment group's consumer lag, and `OrdersDeadLettered` fires on new messages in `orders.dlq`.
- **Licensed MIT.**

### How the incident catalog maps

| # | Incident | Mechanism in shopfront | Expected alert |
| --- | --- | --- | --- |
| 1 | Payment unreachable | Toxiproxy `reset_peer` on checkout → payment | CheckoutErrorRateHigh |
| 2 | Payment network latency | Toxiproxy latency on checkout → payment | CheckoutLatencyHigh |
| 3 | Payment charge bug | `PAYMENT_TOKEN_CACHE=v2`: tokens are cached by card BIN, so cards sharing a BIN get another card's token, which is rejected. About 30% of checkouts fail. | CheckoutErrorRateHigh |
| 4 | Catalog error for one product | `CATALOG_TEXT_NORMALIZATION=ascii`: the ASCII normalizer has no mapping for "é", so `POT-MOKA` returns 500 | CatalogErrorRateHigh |
| 5 | Recommendation memory leak | `RECOMMENDATION_CACHE=v2`: vectors are cached per (session, product) with no eviction. Memory climbs until the container is OOM-killed and restarts, after a few minutes. | RecommendationLatencyHigh / ContainerRestarting |
| 6 | Cart store hang | `docker pause valkey` | CartLatencyHigh, CartErrorRateHigh |
| 7 | Slow order consumer | CPU limit on `fulfillment`; invoice signing costs about 0.3 s of CPU per order. With `--cpus 0.02`, lag reached 54 and the alert fired after 4 minutes. | OrdersBacklogHigh |
| 8 | Bad config release | Shipping redeployed as a new version with a wrong `DATABASE_URL`. It starts, reports connection refused on every quote and shows the new `service.version`. | ShippingErrorRateHigh |
| 9 | Traffic surge | Load generator users ×N | StorefrontTrafficSurge, StorefrontLatencyHigh |
| 10 | Packet loss to catalog | 15% of catalog's outgoing packets dropped (iptables, see ADR 5) | CheckoutLatencyHigh |

Verified on the running stack:

- Pausing Valkey (incident 6) fired the cart, checkout and storefront alerts within 110 s.
- Throttling fulfillment (incident 7) fired the backlog alert.
- A malformed message published by hand was dead-lettered and fired `OrdersDeadLettered`.
- The latent bugs for incidents 3, 4 and 5 were triggered by hand.

Step 4 adds an injection for every incident and tunes the thresholds.

## Consequences

- Footprint: 18 containers plus a one-shot topic initializer, about 1.6 GiB in total (Kafka 364 MiB).
- Discovery now targets an all-Python repo. Polyglot coverage comes from the discovery eval's other sample repos.
- The latent-bug settings are visible in shopfront's `.env`, but their names describe ordinary features. Step 4's leak check has to confirm they don't give the answers away.
