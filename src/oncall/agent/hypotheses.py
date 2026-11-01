"""Hypotheses the agent tracks during an investigation (the hypothesis board, used from v0.2)."""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from oncall.agent.diagnosis import Component, Evidence, FaultType
from oncall.schema import Schema


class HypothesisStatus(StrEnum):
    OPEN = "open"
    SUPPORTED = "supported"
    REJECTED = "rejected"


class Hypothesis(Schema):
    id: str = Field(pattern=r"^h[1-9]\d*$", examples=["h1"])
    statement: str = Field(min_length=1)
    component: Component | None = None
    fault_type: FaultType | None = None
    status: HypothesisStatus = HypothesisStatus.OPEN
    evidence: list[Evidence] = Field(default_factory=list[Evidence])

    @model_validator(mode="after")
    def _decided_with_evidence(self) -> Self:
        if self.status is not HypothesisStatus.OPEN and not self.evidence:
            raise ValueError(f"a {self.status} hypothesis needs evidence")
        return self
