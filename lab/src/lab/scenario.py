"""Incident scenarios: how to inject a fault and what the right diagnosis is."""

import re
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
from pydantic import Field, model_validator

from oncall.agent.diagnosis import Component, EvidenceKind, FaultType
from oncall.schema import Schema

ScenarioId = Annotated[str, Field(pattern=r"^inc_[A-Za-z0-9]{4}$")]
ContainerName = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]*$")]


class Tier(StrEnum):
    PR = "pr"
    NIGHTLY = "nightly"


class Toxic(Schema):
    """A Toxiproxy toxic on one of the lab's proxies (a link between two services)."""

    kind: Literal["toxic"] = "toxic"
    proxy: str
    type: Literal["latency", "reset_peer", "timeout", "bandwidth", "slow_close"]
    stream: Literal["downstream", "upstream"] = "downstream"
    attributes: dict[str, int] = Field(default_factory=dict[str, int])


class Settings(Schema):
    """Redeploy a service with changed environment (settings, version, config)."""

    kind: Literal["settings"] = "settings"
    service: ContainerName
    env: dict[str, str] = Field(min_length=1)


class Pause(Schema):
    kind: Literal["pause"] = "pause"
    container: ContainerName


class CpuLimit(Schema):
    kind: Literal["cpu_limit"] = "cpu_limit"
    container: ContainerName
    cpus: float = Field(gt=0, le=4)


class Netem(Schema):
    """Packet loss and/or delay on a container's network interface (tc netem)."""

    kind: Literal["netem"] = "netem"
    container: ContainerName
    loss_percent: float = Field(default=0, ge=0, le=100)
    delay_ms: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _does_something(self) -> Self:
        if self.loss_percent == 0 and self.delay_ms == 0:
            raise ValueError("netem needs loss_percent or delay_ms")
        return self


class Restart(Schema):
    kind: Literal["restart"] = "restart"
    container: ContainerName


Injection = Annotated[
    Toxic | Settings | Pause | CpuLimit | Netem | Restart, Field(discriminator="kind")
]


class ReadyWhen(Schema):
    alert: str
    timeout_s: int = Field(default=300, gt=0)


class GroundTruth(Schema):
    component: Component | None
    fault_type: FaultType
    mechanism: str = Field(min_length=1)
    acceptable_components: list[Component] = Field(default_factory=list[str])
    required_evidence_kinds: list[EvidenceKind] = Field(default_factory=list[EvidenceKind])

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if (self.fault_type is FaultType.NONE) != (self.component is None):
            raise ValueError("component must be set exactly when there is a fault")
        return self


class Scenario(Schema):
    id: ScenarioId
    title: str
    tier: Tier
    stack: list[Literal["a", "datadog"]] = Field(default_factory=lambda: ["a"], min_length=1)
    injection: list[Injection] = Field(default_factory=list[Injection])
    warmup_s: int = Field(default=120, ge=0)
    ready_when: ReadyWhen | None
    ground_truth: GroundTruth
    canary: str = Field(pattern=r"^cnry-[0-9a-f]{6}$")

    @model_validator(mode="after")
    def _faults_have_a_trigger(self) -> Self:
        fault = self.ground_truth.fault_type is not FaultType.NONE
        if fault and not self.injection:
            raise ValueError("a fault scenario needs an injection")
        if fault and self.ready_when is None:
            raise ValueError("a fault scenario needs ready_when (the alert that starts it)")
        return self


CATALOG_DIR = Path(__file__).resolve().parents[2] / "catalog"


def load(path: Path) -> Scenario:
    scenario = Scenario.model_validate(yaml.safe_load(path.read_text()))
    if path.parent.name != scenario.id:
        raise ValueError(f"{path}: directory name must equal the scenario id {scenario.id}")
    return scenario


def load_catalog(directory: Path = CATALOG_DIR) -> dict[str, Scenario]:
    scenarios = [load(p) for p in sorted(directory.glob("*/scenario.yaml"))]
    catalog = {s.id: s for s in scenarios}
    if len(catalog) != len(scenarios):
        raise ValueError("duplicate scenario ids in the catalog")
    return catalog


def find(catalog: dict[str, Scenario], key: str) -> Scenario:
    """Look a scenario up by id, or by a unique case-insensitive substring of its title."""
    if key in catalog:
        return catalog[key]
    matches = [s for s in catalog.values() if re.search(re.escape(key), s.title, re.IGNORECASE)]
    if len(matches) != 1:
        raise KeyError(f"no unique scenario matches {key!r}")
    return matches[0]
