"""`get_resource_usage`: leaks, CPU starvation, crash loops."""

from typing import Annotated

from pydantic import Field

from oncall.capabilities.common import Item, Result, ServiceName, TimeRange
from oncall.schema import Schema

Percent = Annotated[float, Field(ge=0)]  # can exceed 100 with several cores
Bytes = Annotated[int, Field(ge=0)]
Count = Annotated[int, Field(ge=0)]


class GetResourceUsageInput(Schema):
    service: ServiceName
    time_range: TimeRange | None = None


class ResourceUsage(Item):
    service: ServiceName
    instance: str = Field(description="Container or pod the numbers belong to.")
    cpu_percent_avg: Percent
    cpu_percent_max: Percent
    cpu_throttled_ratio: float | None = Field(
        default=None, ge=0, le=1, description="Share of CPU periods throttled, if known."
    )
    memory_start_bytes: Bytes
    memory_end_bytes: Bytes
    memory_max_bytes: Bytes
    memory_limit_bytes: Bytes | None = None
    restarts: Count
    oom_kills: Count


class GetResourceUsageOutput(Result):
    instances: list[ResourceUsage]
