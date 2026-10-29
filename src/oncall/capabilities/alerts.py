"""`list_alerts`: the starting point of an investigation and the alerts correlated with it."""

from enum import StrEnum

from pydantic import AwareDatetime

from oncall.capabilities.common import Item, Result, TimeRange
from oncall.schema import Schema


class AlertState(StrEnum):
    PENDING = "pending"
    FIRING = "firing"
    RESOLVED = "resolved"


class ListAlertsInput(Schema):
    time_range: TimeRange | None = None
    state: AlertState | None = None


class Alert(Item):
    name: str
    state: AlertState
    labels: dict[str, str]
    started_at: AwareDatetime
    ended_at: AwareDatetime | None = None
    value: float | None = None
    summary: str | None = None


class ListAlertsOutput(Result):
    alerts: list[Alert]
