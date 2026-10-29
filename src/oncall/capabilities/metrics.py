"""`query_metric`: anything numeric, through a structured query (never raw PromQL)."""

from enum import StrEnum

from pydantic import AwareDatetime, Field

from oncall.capabilities.common import Item, LabelName, MetricName, Result, TimeRange
from oncall.schema import Schema


class Aggregation(StrEnum):
    AVG = "avg"
    SUM = "sum"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    RATE = "rate"
    P50 = "p50"
    P95 = "p95"
    P99 = "p99"


class QueryMetricInput(Schema):
    metric: MetricName
    agg: Aggregation
    filters: dict[LabelName, str] = Field(default_factory=dict[LabelName, str])
    group_by: list[LabelName] = Field(default_factory=list[LabelName], max_length=5)
    step_s: int = Field(default=60, ge=10, le=3600)
    time_range: TimeRange | None = None


class Point(Schema):
    ts: AwareDatetime
    value: float


class SeriesStats(Schema):
    min: float
    max: float
    mean: float
    last: float


class Series(Item):
    labels: dict[str, str]
    points: list[Point]
    stats: SeriesStats | None = Field(default=None, description="None when the series is empty.")


class QueryMetricOutput(Result):
    series: list[Series]
