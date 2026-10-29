"""The capabilities the agent can call. Names and schemas here are the stable contract."""

from dataclasses import dataclass

from oncall.capabilities.alerts import ListAlertsInput, ListAlertsOutput
from oncall.capabilities.health import GetServiceHealthInput, GetServiceHealthOutput
from oncall.capabilities.logs import SearchLogsInput, SearchLogsOutput
from oncall.capabilities.metrics import QueryMetricInput, QueryMetricOutput
from oncall.capabilities.resources import GetResourceUsageInput, GetResourceUsageOutput
from oncall.capabilities.traces import (
    GetTraceInput,
    GetTraceOutput,
    SearchTracesInput,
    SearchTracesOutput,
)
from oncall.schema import Schema


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    description: str
    input: type[Schema]
    output: type[Schema]


CAPABILITIES: dict[str, CapabilitySpec] = {
    spec.name: spec
    for spec in [
        CapabilitySpec(
            "list_alerts",
            "List alerts in a time range: the starting point and any correlated alerts.",
            ListAlertsInput,
            ListAlertsOutput,
        ),
        CapabilitySpec(
            "get_service_health",
            "Request rate, error ratio and latency per service, compared with a baseline.",
            GetServiceHealthInput,
            GetServiceHealthOutput,
        ),
        CapabilitySpec(
            "search_traces",
            "Find traces of a service, filtered by operation, status or minimum duration.",
            SearchTracesInput,
            SearchTracesOutput,
        ),
        CapabilitySpec(
            "get_trace",
            "Fetch every span of one trace.",
            GetTraceInput,
            GetTraceOutput,
        ),
        CapabilitySpec(
            "search_logs",
            "Search log records by service, text, attributes and minimum severity.",
            SearchLogsInput,
            SearchLogsOutput,
        ),
        CapabilitySpec(
            "query_metric",
            "Query one metric with an aggregation, label filters and grouping.",
            QueryMetricInput,
            QueryMetricOutput,
        ),
        CapabilitySpec(
            "get_resource_usage",
            "CPU, throttling, memory, restarts and OOM kills per instance of a service.",
            GetResourceUsageInput,
            GetResourceUsageOutput,
        ),
    ]
}
