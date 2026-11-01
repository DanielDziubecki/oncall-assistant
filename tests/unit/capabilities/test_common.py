from datetime import UTC, datetime, timedelta

import pytest
from pydantic import TypeAdapter, ValidationError

from oncall.capabilities.common import (
    DEFAULT_WINDOW,
    MAX_WINDOW,
    Ref,
    TimeRange,
    make_ref,
    parse_ref,
    resolve_time_range,
)

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
ref_adapter: TypeAdapter[str] = TypeAdapter(Ref)


def test_ref_round_trips() -> None:
    ref = make_ref(42, 3)

    assert ref == "e42#3"
    assert parse_ref(ref) == (42, 3)
    assert ref_adapter.validate_python(ref) == ref


@pytest.mark.parametrize("bad", ["42#3", "e0#1", "e01#1", "e4#-1", "e4", "e4#3 ", "E4#3"])
def test_malformed_refs_are_rejected(bad: str) -> None:
    with pytest.raises(ValueError, match="not a ref"):
        parse_ref(bad)
    with pytest.raises(ValidationError):
        ref_adapter.validate_python(bad)


@pytest.mark.parametrize(("event_id", "index"), [(0, 0), (1, -1)])
def test_make_ref_rejects_invalid_parts(event_id: int, index: int) -> None:
    with pytest.raises(ValueError, match="invalid ref parts"):
        make_ref(event_id, index)


def test_time_range_requires_start_before_end() -> None:
    with pytest.raises(ValidationError, match="start must be before end"):
        TimeRange(start=NOW, end=NOW)


def test_time_range_rejects_naive_datetimes() -> None:
    with pytest.raises(ValidationError):
        TimeRange.model_validate({"start": "2026-10-29T11:00:00", "end": "2026-10-29T12:00:00"})


def test_time_range_parses_json() -> None:
    tr = TimeRange.model_validate_json(
        '{"start": "2026-10-29T11:00:00Z", "end": "2026-10-29T12:00:00Z"}'
    )

    assert tr.duration == timedelta(hours=1)


def test_missing_time_range_defaults_to_last_hour() -> None:
    assert resolve_time_range(None, NOW) == TimeRange(start=NOW - DEFAULT_WINDOW, end=NOW)


def test_long_time_range_is_capped_keeping_the_end() -> None:
    requested = TimeRange(start=NOW - timedelta(days=30), end=NOW - timedelta(hours=2))

    resolved = resolve_time_range(requested, NOW)

    assert resolved.end == requested.end
    assert resolved.duration == MAX_WINDOW


def test_future_end_is_clamped_to_now() -> None:
    requested = TimeRange(start=NOW - timedelta(hours=1), end=NOW + timedelta(hours=1))

    assert resolve_time_range(requested, NOW).end == NOW


def test_range_entirely_in_the_future_is_rejected() -> None:
    requested = TimeRange(start=NOW + timedelta(hours=1), end=NOW + timedelta(hours=2))

    with pytest.raises(ValueError, match="future"):
        resolve_time_range(requested, NOW)


def test_range_within_limits_is_unchanged() -> None:
    requested = TimeRange(start=NOW - timedelta(hours=3), end=NOW - timedelta(hours=1))

    assert resolve_time_range(requested, NOW) == requested
