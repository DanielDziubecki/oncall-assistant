"""`search_traces` and `get_trace`: slow or failing request paths, and where an error started."""

from enum import StrEnum
from typing import Annotated

from pydantic import AwareDatetime, Field

from oncall.capabilities.common import Item, Result, ServiceName, SpanStatus, TimeRange
from oncall.schema import Schema

TraceId = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$", description="W3C trace id, 32 hex.")]
SpanId = Annotated[str, Field(pattern=r"^[0-9a-f]{16}$", description="W3C span id, 16 hex.")]
DurationMs = Annotated[float, Field(ge=0)]


class SpanKind(StrEnum):
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"
    INTERNAL = "internal"


class SearchTracesInput(Schema):
    service: ServiceName
    operation: str | None = None
    status: SpanStatus | None = None
    min_duration_ms: DurationMs | None = None
    time_range: TimeRange | None = None
    limit: int = Field(default=20, ge=1, le=50)


class ErrorSpan(Schema):
    service: ServiceName
    operation: str
    message: str | None = None


class TraceSummary(Item):
    trace_id: TraceId
    root_service: ServiceName
    root_operation: str
    start: AwareDatetime
    duration_ms: DurationMs
    span_count: int = Field(ge=1)
    error_span: ErrorSpan | None = Field(
        default=None, description="The deepest span with error status, if any."
    )


class SearchTracesOutput(Result):
    traces: list[TraceSummary]


class GetTraceInput(Schema):
    trace_id: TraceId
    time_range: TimeRange | None = Field(
        default=None, description="Optional hint that narrows the backend lookup."
    )


class Span(Item):
    span_id: SpanId
    parent_span_id: SpanId | None
    service: ServiceName
    operation: str
    kind: SpanKind
    start: AwareDatetime
    duration_ms: DurationMs
    status: SpanStatus
    status_message: str | None = None
    attributes: dict[str, str] = Field(default_factory=dict[str, str])


class GetTraceOutput(Result):
    trace_id: TraceId
    spans: list[Span] = Field(description="Flat list; rebuild the tree from parent_span_id.")
