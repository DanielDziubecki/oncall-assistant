import os
import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from lab.scenario import Scenario, Tier, find, load_catalog
from pydantic import ValidationError

from oncall.agent.diagnosis import FaultType

CATALOG = load_catalog()
TARGET = Path(os.environ.get("LAB_TARGET", Path(__file__).resolve().parents[3] / "shopfront"))


def test_catalog_has_ten_incidents_and_three_baselines() -> None:
    faults = [s for s in CATALOG.values() if s.ground_truth.fault_type is not FaultType.NONE]
    baselines = [s for s in CATALOG.values() if s.ground_truth.fault_type is FaultType.NONE]

    assert len(faults) == 10
    assert len(baselines) == 3


def test_every_fault_type_is_covered() -> None:
    # cpu_saturation has no incident in the first ten; it arrives with the larger catalog.
    covered = {s.ground_truth.fault_type for s in CATALOG.values()}

    assert covered == set(FaultType) - {FaultType.CPU_SATURATION}


def test_pr_tier_is_the_planned_subset() -> None:
    pr = {s.title for s in CATALOG.values() if s.tier is Tier.PR}

    assert pr == {
        "Payment unreachable",
        "Payment network latency",
        "Payment charge bug",
        "Cart store hang",
        "No fault (baseline 1)",
    }


def test_canaries_are_unique() -> None:
    canaries = [s.canary for s in CATALOG.values()]

    assert len(set(canaries)) == len(canaries)


@pytest.mark.skipif(not (TARGET / "alerts").is_dir(), reason="target checkout not available")
def test_every_trigger_alert_exists_in_the_target() -> None:
    defined = set(re.findall(r"- alert: (\w+)", (TARGET / "alerts" / "slo.rules.yml").read_text()))
    triggers = {s.ready_when.alert for s in CATALOG.values() if s.ready_when}

    assert triggers <= defined


def _scenario(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "id": "inc_Test",
        "title": "test",
        "tier": "pr",
        "injection": [{"kind": "pause", "container": "valkey"}],
        "ready_when": {"alert": "CartLatencyHigh"},
        "ground_truth": {
            "component": "valkey",
            "fault_type": "dependency_unreachable",
            "mechanism": "m",
        },
        "canary": "cnry-abc123",
    }
    return {**base, **overrides}


def test_fault_without_injection_is_rejected() -> None:
    with pytest.raises(ValidationError, match="needs an injection"):
        Scenario.model_validate(_scenario(injection=[]))


def test_fault_without_trigger_alert_is_rejected() -> None:
    with pytest.raises(ValidationError, match="ready_when"):
        Scenario.model_validate(_scenario(ready_when=None))


def test_no_fault_must_not_name_a_component() -> None:
    gt = {"component": "valkey", "fault_type": "none", "mechanism": "m"}

    with pytest.raises(ValidationError, match="component must be set exactly"):
        Scenario.model_validate(_scenario(ground_truth=gt, injection=[], ready_when=None))


def test_netem_needs_an_effect() -> None:
    with pytest.raises(ValidationError, match="netem needs"):
        Scenario.model_validate(_scenario(injection=[{"kind": "netem", "container": "catalog"}]))


def test_unknown_injection_kind_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Scenario.model_validate(_scenario(injection=[{"kind": "rm-rf", "container": "x"}]))


def test_directory_must_match_id(tmp_path: Path) -> None:
    (tmp_path / "inc_Wrng").mkdir()
    (tmp_path / "inc_Wrng" / "scenario.yaml").write_text(yaml.safe_dump(_scenario()))

    with pytest.raises(ValueError, match="directory name"):
        load_catalog(tmp_path)


def test_find_by_id_or_title() -> None:
    scenario = next(iter(CATALOG.values()))

    assert find(CATALOG, scenario.id) is scenario
    assert find(CATALOG, "cart store").title == "Cart store hang"
    with pytest.raises(KeyError):
        find(CATALOG, "payment")  # ambiguous
