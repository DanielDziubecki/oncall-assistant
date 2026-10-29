from typing import Any

import pytest
from pydantic import ValidationError

from oncall.capabilities.registry import CAPABILITIES
from oncall.capabilities.traces import GetTraceOutput

T0 = "2026-10-29T11:00:00Z"
T1 = "2026-10-29T12:00:00Z"
TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
SPAN_ID = "00f067aa0ba902b7"
SPAN_ID_2 = "b7ad6b7169203331"
STATS = {"rps": 12.5, "error_ratio": 0.31, "p50_ms": 40.0, "p99_ms": 2900.0}

# One realistic input and output per capability, as an adapter or the LLM would produce them.
EXAMPLES: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
    "list_alerts": (
        {"state": "firing"},
        {
            "alerts": [
                {
                    "ref": "e1#0",
                    "name": "CheckoutErrorRateHigh",
                    "state": "firing",
                    "labels": {"service": "checkout", "severity": "page"},
                    "started_at": T0,
                    "value": 0.31,
                }
            ]
        },
    ),
    "get_service_health": (
        {"service": "checkout", "time_range": {"start": T0, "end": T1}},
        {"services": [{"ref": "e2#0", "service": "checkout", "current": STATS, "baseline": STATS}]},
    ),
    "search_traces": (
        {"service": "checkout", "status": "error", "min_duration_ms": 1000, "limit": 10},
        {
            "traces": [
                {
                    "ref": "e3#0",
                    "trace_id": TRACE_ID,
                    "root_service": "frontend",
                    "root_operation": "POST /api/checkout",
                    "start": T0,
                    "duration_ms": 3012.5,
                    "span_count": 14,
                    "error_span": {
                        "service": "checkout",
                        "operation": "oteldemo.PaymentService/Charge",
                        "message": "code = Unavailable",
                    },
                }
            ],
            "truncated": True,
        },
    ),
    "get_trace": (
        {"trace_id": TRACE_ID},
        {
            "trace_id": TRACE_ID,
            "spans": [
                {
                    "ref": "e4#0",
                    "span_id": SPAN_ID,
                    "parent_span_id": None,
                    "service": "frontend",
                    "operation": "POST /api/checkout",
                    "kind": "server",
                    "start": T0,
                    "duration_ms": 3012.5,
                    "status": "error",
                },
                {
                    "ref": "e4#1",
                    "span_id": SPAN_ID_2,
                    "parent_span_id": SPAN_ID,
                    "service": "checkout",
                    "operation": "oteldemo.PaymentService/Charge",
                    "kind": "client",
                    "start": T0,
                    "duration_ms": 3001.0,
                    "status": "error",
                    "status_message": "connection reset by peer",
                    "attributes": {"rpc.system": "grpc", "net.peer.name": "payment"},
                },
            ],
        },
    ),
    "search_logs": (
        {"service": "checkout", "text": "UNAVAILABLE", "min_severity": "warn"},
        {
            "records": [
                {
                    "ref": "e5#0",
                    "timestamp": T0,
                    "service": "checkout",
                    "severity": "error",
                    "body": "failed to charge card: rpc error: code = Unavailable",
                    "trace_id": TRACE_ID,
                    "span_id": SPAN_ID_2,
                }
            ]
        },
    ),
    "query_metric": (
        {
            "metric": "traces_spanmetrics_calls_total",
            "agg": "rate",
            "filters": {"service_name": "checkout", "status_code": "STATUS_CODE_ERROR"},
            "group_by": ["span_name"],
            "step_s": 30,
        },
        {
            "series": [
                {
                    "ref": "e6#0",
                    "labels": {"span_name": "oteldemo.PaymentService/Charge"},
                    "points": [{"ts": T0, "value": 0.0}, {"ts": T1, "value": 4.2}],
                    "stats": {"min": 0.0, "max": 4.2, "mean": 2.1, "last": 4.2},
                },
                {"ref": "e6#1", "labels": {"span_name": "idle"}, "points": []},
            ]
        },
    ),
    "get_resource_usage": (
        {"service": "recommendation"},
        {
            "instances": [
                {
                    "ref": "e7#0",
                    "service": "recommendation",
                    "instance": "shopfront-recommendation-1",
                    "cpu_percent_avg": 35.0,
                    "cpu_percent_max": 180.0,
                    "cpu_throttled_ratio": 0.02,
                    "memory_start_bytes": 200_000_000,
                    "memory_end_bytes": 480_000_000,
                    "memory_max_bytes": 495_000_000,
                    "memory_limit_bytes": 500_000_000,
                    "restarts": 2,
                    "oom_kills": 2,
                }
            ]
        },
    ),
}


def test_registry_has_the_first_seven_capabilities() -> None:
    assert set(CAPABILITIES) == {
        "list_alerts",
        "get_service_health",
        "search_traces",
        "get_trace",
        "search_logs",
        "query_metric",
        "get_resource_usage",
    }
    assert set(EXAMPLES) == set(CAPABILITIES)


@pytest.mark.parametrize("name", sorted(CAPABILITIES))
def test_examples_validate_and_round_trip_through_json(name: str) -> None:
    spec = CAPABILITIES[name]
    raw_input, raw_output = EXAMPLES[name]

    for model, raw in ((spec.input, raw_input), (spec.output, raw_output)):
        parsed = model.model_validate(raw)
        assert model.model_validate_json(parsed.model_dump_json()) == parsed


@pytest.mark.parametrize("name", sorted(CAPABILITIES))
def test_unknown_fields_are_rejected(name: str) -> None:
    spec = CAPABILITIES[name]
    raw_input, raw_output = EXAMPLES[name]

    with pytest.raises(ValidationError, match="extra_forbidden"):
        spec.input.model_validate({**raw_input, "promql": "up"})
    with pytest.raises(ValidationError, match="extra_forbidden"):
        spec.output.model_validate({**raw_output, "debug": True})


@pytest.mark.parametrize("name", sorted(CAPABILITIES))
def test_every_output_item_requires_a_valid_ref(name: str) -> None:
    spec = CAPABILITIES[name]
    raw_output = EXAMPLES[name][1]
    list_field = next(key for key, value in raw_output.items() if isinstance(value, list))
    items: list[dict[str, Any]] = raw_output[list_field]
    first = items[0]

    without_ref = {k: v for k, v in first.items() if k != "ref"}
    with pytest.raises(ValidationError, match="ref"):
        spec.output.model_validate({**raw_output, list_field: [without_ref]})
    with pytest.raises(ValidationError, match="ref"):
        spec.output.model_validate({**raw_output, list_field: [{**first, "ref": "trace-1"}]})


@pytest.mark.parametrize("name", sorted(CAPABILITIES))
def test_models_are_immutable(name: str) -> None:
    parsed = CAPABILITIES[name].input.model_validate(EXAMPLES[name][0])

    with pytest.raises(ValidationError, match="frozen"):
        parsed.time_range = None  # pyright: ignore[reportAttributeAccessIssue]


@pytest.mark.parametrize(
    "metric",
    [
        "rate(http_requests_total[5m])",
        'up{job="x"}',
        "sum by (a) (b)",
        "1metric",
        "",
    ],
)
def test_query_metric_rejects_anything_but_a_metric_name(metric: str) -> None:
    raw_input = {**EXAMPLES["query_metric"][0], "metric": metric}

    with pytest.raises(ValidationError, match="metric"):
        CAPABILITIES["query_metric"].input.model_validate(raw_input)


@pytest.mark.parametrize("metric", ["http_server_duration_seconds", "trace.http.request.hits"])
def test_query_metric_accepts_prometheus_and_datadog_names(metric: str) -> None:
    raw_input = {**EXAMPLES["query_metric"][0], "metric": metric}

    CAPABILITIES["query_metric"].input.model_validate(raw_input)


@pytest.mark.parametrize("limit", [0, 51])
def test_search_traces_limit_is_bounded(limit: int) -> None:
    raw_input = {**EXAMPLES["search_traces"][0], "limit": limit}

    with pytest.raises(ValidationError, match="limit"):
        CAPABILITIES["search_traces"].input.model_validate(raw_input)


@pytest.mark.parametrize("trace_id", ["abc", TRACE_ID.upper(), TRACE_ID + "0"])
def test_trace_ids_must_be_w3c_hex(trace_id: str) -> None:
    with pytest.raises(ValidationError, match="trace_id"):
        CAPABILITIES["get_trace"].input.model_validate({"trace_id": trace_id})


def test_service_health_error_ratio_is_a_fraction() -> None:
    service = EXAMPLES["get_service_health"][1]["services"][0]
    bad = {**service, "current": {**STATS, "error_ratio": 31.0}}

    with pytest.raises(ValidationError, match="error_ratio"):
        CAPABILITIES["get_service_health"].output.model_validate({"services": [bad]})


def test_trace_spans_link_to_their_parent() -> None:
    trace = GetTraceOutput.model_validate(EXAMPLES["get_trace"][1])
    by_id = {span.span_id: span for span in trace.spans}

    child = trace.spans[1]
    assert child.parent_span_id is not None
    assert by_id[child.parent_span_id].service == "frontend"
