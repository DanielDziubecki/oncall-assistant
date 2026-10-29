"""What the agent concludes: ranked root causes, each backed by evidence citing tool results."""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field, model_validator

from oncall.capabilities.common import Ref
from oncall.schema import Schema

Probability = Annotated[float, Field(ge=0, le=1)]

_NAME = r"[A-Za-z0-9][A-Za-z0-9_.\-]*"

# A service (`payment`), a dependency (`valkey-cart`) or a link between two (`checkout->payment`).
Component = Annotated[str, Field(max_length=200, pattern=rf"^{_NAME}(->{_NAME})?$")]


class FaultType(StrEnum):
    DEPENDENCY_UNREACHABLE = "dependency_unreachable"
    NETWORK_LATENCY = "network_latency"
    PACKET_LOSS = "packet_loss"
    APPLICATION_ERROR = "application_error"
    MEMORY_LEAK = "memory_leak"
    CPU_SATURATION = "cpu_saturation"
    SLOW_CONSUMER = "slow_consumer"
    BAD_CONFIG_DEPLOY = "bad_config_deploy"
    TRAFFIC_SURGE = "traffic_surge"
    NONE = "none"


class EvidenceKind(StrEnum):
    ALERT = "alert"
    METRIC = "metric"
    TRACE = "trace"
    LOG = "log"
    RESOURCE = "resource"


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


def confidence_level(p: float) -> ConfidenceLevel:
    if p >= 0.7:
        return ConfidenceLevel.HIGH
    if p >= 0.4:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


class Evidence(Schema):
    """A claim tied to one recorded tool result item, with a value the verifier can check."""

    ref: Ref
    kind: EvidenceKind
    claim: str = Field(min_length=1, description="What this item shows, in one sentence.")
    quote: str | None = Field(
        default=None,
        min_length=1,
        description="Exact text from the item: a trace id, span id or log substring.",
    )
    value: float | None = Field(
        default=None, description="A number from the item, e.g. a metric value or error ratio."
    )

    @model_validator(mode="after")
    def _checkable(self) -> Self:
        if self.quote is None and self.value is None:
            raise ValueError("evidence needs a quote or a value the verifier can check")
        return self


class RootCause(Schema):
    component: Component | None = Field(description="None only when fault_type is none.")
    fault_type: FaultType
    mechanism: str = Field(min_length=1, description="How the fault produces the symptoms.")
    confidence: Probability
    evidence: list[Evidence]

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.fault_type is FaultType.NONE:
            if self.component is not None:
                raise ValueError("fault_type none must not name a component")
        else:
            if self.component is None:
                raise ValueError("a fault needs a component")
            if not self.evidence:
                raise ValueError("a fault needs at least one piece of evidence")
        return self

    @property
    def confidence_level(self) -> ConfidenceLevel:
        return confidence_level(self.confidence)


class ProposedFix(Schema):
    """Advisory only: a human approves or rejects it, nothing is executed."""

    summary: str = Field(min_length=1)
    steps: list[str] = Field(default_factory=list[str])
    risk: str | None = None


class Diagnosis(Schema):
    summary: str = Field(min_length=1)
    root_causes: list[RootCause] = Field(
        min_length=1, max_length=3, description="Most likely first; scored as top-1 and top-3."
    )
    proposed_fix: ProposedFix | None = None
    unchecked: list[str] = Field(
        default_factory=list[str],
        description="What could not be checked (tool errors, missing access) and why.",
    )

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        confidences = [cause.confidence for cause in self.root_causes]
        if confidences != sorted(confidences, reverse=True):
            raise ValueError("root_causes must be ordered by confidence, highest first")
        return self

    @property
    def top(self) -> RootCause:
        return self.root_causes[0]

    @property
    def evidence(self) -> list[Evidence]:
        return [item for cause in self.root_causes for item in cause.evidence]
