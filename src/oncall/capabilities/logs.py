"""`search_logs`: exceptions, connection refused, timeouts."""

from pydantic import AwareDatetime, Field

from oncall.capabilities.common import Item, LabelName, Result, ServiceName, Severity, TimeRange
from oncall.capabilities.traces import SpanId, TraceId
from oncall.schema import Schema


class SearchLogsInput(Schema):
    service: ServiceName | None = None
    text: str | None = Field(
        default=None, max_length=200, description="Plain substring match on the body, not a regex."
    )
    filters: dict[LabelName, str] = Field(default_factory=dict[LabelName, str])
    min_severity: Severity | None = None
    time_range: TimeRange | None = None
    limit: int = Field(default=50, ge=1, le=200)


class LogRecord(Item):
    timestamp: AwareDatetime
    service: ServiceName
    severity: Severity
    body: str
    trace_id: TraceId | None = None
    span_id: SpanId | None = None


class SearchLogsOutput(Result):
    records: list[LogRecord]
