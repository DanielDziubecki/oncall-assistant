"""Vendor-neutral, read-only capabilities. Backends plug in behind these schemas."""

from oncall.capabilities.common import Ref, TimeRange, make_ref, parse_ref, resolve_time_range
from oncall.capabilities.registry import CAPABILITIES, CapabilitySpec

__all__ = [
    "CAPABILITIES",
    "CapabilitySpec",
    "Ref",
    "TimeRange",
    "make_ref",
    "parse_ref",
    "resolve_time_range",
]
