"""Types shared by all capabilities: time ranges, evidence refs, names and enums."""

import re
from datetime import timedelta
from enum import StrEnum
from typing import Annotated, Self

from pydantic import AwareDatetime, Field, model_validator

from oncall.schema import Schema

DEFAULT_WINDOW = timedelta(hours=1)
MAX_WINDOW = timedelta(hours=24)

_REF_RE = re.compile(r"^e([1-9]\d*)#(\d+)$")

Ref = Annotated[
    str,
    Field(
        pattern=_REF_RE.pattern,
        description="Citation of one item in a recorded tool result: e<event_id>#<index>.",
        examples=["e42#3"],
    ),
]

ServiceName = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.\-]*$"),
]

# Prometheus (`a_b:c`) and Datadog (`a.b.c`) names. Never a query expression.
MetricName = Annotated[
    str,
    Field(min_length=1, max_length=200, pattern=r"^[A-Za-z_:][A-Za-z0-9_:.]*$"),
]

LabelName = Annotated[
    str,
    Field(min_length=1, max_length=100, pattern=r"^[A-Za-z_][A-Za-z0-9_.]*$"),
]


def make_ref(event_id: int, index: int) -> str:
    if event_id < 1 or index < 0:
        raise ValueError(f"invalid ref parts: event_id={event_id}, index={index}")
    return f"e{event_id}#{index}"


def parse_ref(ref: str) -> tuple[int, int]:
    """Return (event_id, index) for a ref like `e42#3`."""
    match = _REF_RE.fullmatch(ref)
    if match is None:
        raise ValueError(f"not a ref: {ref!r}")
    return int(match.group(1)), int(match.group(2))


class TimeRange(Schema):
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def _start_before_end(self) -> Self:
        if self.start >= self.end:
            raise ValueError("start must be before end")
        return self

    @property
    def duration(self) -> timedelta:
        return self.end - self.start


def resolve_time_range(requested: TimeRange | None, now: AwareDatetime) -> TimeRange:
    """Apply the proxy's limits: default to the last hour, cap at 24 h, never past `now`.

    `now` is passed in so evals can pin the clock to the incident time.
    """
    if requested is None:
        return TimeRange(start=now - DEFAULT_WINDOW, end=now)
    end = min(requested.end, now)
    start = max(requested.start, end - MAX_WINDOW)
    if start >= end:
        raise ValueError("time range lies entirely in the future")
    return TimeRange(start=start, end=end)


class Item(Schema):
    """One element of a capability result. The agent must cite `ref` as evidence."""

    ref: Ref


class Result(Schema):
    truncated: bool = Field(
        default=False, description="True when the backend had more items than were returned."
    )


class Severity(StrEnum):
    TRACE = "trace"
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    FATAL = "fatal"


class SpanStatus(StrEnum):
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"
