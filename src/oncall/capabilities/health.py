"""`get_service_health`: RED metrics per service, to find which service degraded first."""

from typing import Annotated

from pydantic import Field

from oncall.capabilities.common import Item, Result, ServiceName, TimeRange
from oncall.schema import Schema

NonNegative = Annotated[float, Field(ge=0)]
Ratio = Annotated[float, Field(ge=0, le=1)]


class GetServiceHealthInput(Schema):
    service: ServiceName | None = Field(default=None, description="Omit for all services.")
    time_range: TimeRange | None = None


class HealthStats(Schema):
    rps: NonNegative
    error_ratio: Ratio = Field(description="Failed requests / all requests, 0 to 1.")
    p50_ms: NonNegative
    p99_ms: NonNegative


class ServiceHealth(Item):
    service: ServiceName
    current: HealthStats
    baseline: HealthStats | None = Field(
        default=None, description="Same stats for the comparable period before the range."
    )


class GetServiceHealthOutput(Result):
    services: list[ServiceHealth]
