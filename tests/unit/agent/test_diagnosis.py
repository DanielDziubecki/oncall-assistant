from typing import Any

import pytest
from pydantic import ValidationError

from oncall.agent.diagnosis import ConfidenceLevel, Diagnosis, Evidence, FaultType, RootCause
from oncall.agent.hypotheses import Hypothesis, HypothesisStatus

TRACE_EVIDENCE: dict[str, Any] = {
    "ref": "e4#1",
    "kind": "trace",
    "claim": "checkout's call to payment fails with connection reset after 3 s",
    "quote": "4bf92f3577b34da6a3ce929d0e0e4736",
}
METRIC_EVIDENCE: dict[str, Any] = {
    "ref": "e6#0",
    "kind": "metric",
    "claim": "checkout error rate on Charge rose from 0 to 4.2/s",
    "value": 4.2,
}


def cause(**overrides: Any) -> dict[str, Any]:
    return {
        "component": "payment",
        "fault_type": "dependency_unreachable",
        "mechanism": "payment resets connections, so checkout's Charge calls fail",
        "confidence": 0.8,
        "evidence": [TRACE_EVIDENCE, METRIC_EVIDENCE],
        **overrides,
    }


def test_full_diagnosis_round_trips_through_json() -> None:
    diagnosis = Diagnosis.model_validate(
        {
            "summary": "Checkout fails because payment is unreachable.",
            "root_causes": [
                cause(),
                cause(component="checkout->payment", fault_type="network_latency", confidence=0.15),
            ],
            "proposed_fix": {"summary": "Restart payment", "steps": ["check payment health"]},
            "unchecked": ["get_resource_usage returned permission denied"],
        }
    )

    assert Diagnosis.model_validate_json(diagnosis.model_dump_json()) == diagnosis
    assert diagnosis.top.fault_type is FaultType.DEPENDENCY_UNREACHABLE
    assert diagnosis.top.confidence_level is ConfidenceLevel.HIGH
    assert [e.ref for e in diagnosis.evidence] == ["e4#1", "e6#0", "e4#1", "e6#0"]


def test_no_fault_diagnosis_needs_no_component_or_evidence() -> None:
    diagnosis = Diagnosis.model_validate(
        {
            "summary": "No incident: traffic and errors are within baseline.",
            "root_causes": [cause(component=None, fault_type="none", evidence=[])],
        }
    )

    assert diagnosis.top.fault_type is FaultType.NONE


def test_no_fault_must_not_name_a_component() -> None:
    with pytest.raises(ValidationError, match="must not name a component"):
        RootCause.model_validate(cause(fault_type="none"))


def test_fault_needs_a_component() -> None:
    with pytest.raises(ValidationError, match="needs a component"):
        RootCause.model_validate(cause(component=None))


def test_fault_needs_evidence() -> None:
    with pytest.raises(ValidationError, match="at least one piece of evidence"):
        RootCause.model_validate(cause(evidence=[]))


def test_evidence_needs_something_checkable() -> None:
    raw = {k: v for k, v in TRACE_EVIDENCE.items() if k != "quote"}

    with pytest.raises(ValidationError, match="quote or a value"):
        Evidence.model_validate(raw)


def test_evidence_ref_must_be_well_formed() -> None:
    with pytest.raises(ValidationError, match="ref"):
        Evidence.model_validate({**TRACE_EVIDENCE, "ref": "4bf92f35"})


@pytest.mark.parametrize("count", [0, 4])
def test_one_to_three_root_causes(count: int) -> None:
    causes = [cause(confidence=0.5)] * count

    with pytest.raises(ValidationError, match="root_causes"):
        Diagnosis.model_validate({"summary": "x", "root_causes": causes})


def test_root_causes_are_ordered_by_confidence() -> None:
    with pytest.raises(ValidationError, match="highest first"):
        Diagnosis.model_validate(
            {"summary": "x", "root_causes": [cause(confidence=0.2), cause(confidence=0.6)]}
        )


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_confidence_is_a_probability(confidence: float) -> None:
    with pytest.raises(ValidationError, match="confidence"):
        RootCause.model_validate(cause(confidence=confidence))


@pytest.mark.parametrize(
    ("confidence", "level"),
    [
        (0.0, ConfidenceLevel.LOW),
        (0.39, ConfidenceLevel.LOW),
        (0.4, ConfidenceLevel.MEDIUM),
        (0.69, ConfidenceLevel.MEDIUM),
        (0.7, ConfidenceLevel.HIGH),
        (1.0, ConfidenceLevel.HIGH),
    ],
)
def test_confidence_levels(confidence: float, level: ConfidenceLevel) -> None:
    assert RootCause.model_validate(cause(confidence=confidence)).confidence_level is level


@pytest.mark.parametrize("component", ["payment", "valkey-cart", "checkout->payment"])
def test_valid_components(component: str) -> None:
    RootCause.model_validate(cause(component=component))


@pytest.mark.parametrize("component", ["", "checkout -> payment", "a->b->c", "->payment"])
def test_invalid_components(component: str) -> None:
    with pytest.raises(ValidationError, match="component"):
        RootCause.model_validate(cause(component=component))


def test_unknown_fault_type_is_rejected() -> None:
    with pytest.raises(ValidationError, match="fault_type"):
        RootCause.model_validate(cause(fault_type="gremlins"))


def test_open_hypothesis_needs_no_evidence() -> None:
    hypothesis = Hypothesis(id="h1", statement="payment is down")

    assert hypothesis.status is HypothesisStatus.OPEN


@pytest.mark.parametrize("status", ["supported", "rejected"])
def test_decided_hypothesis_needs_evidence(status: str) -> None:
    with pytest.raises(ValidationError, match="needs evidence"):
        Hypothesis.model_validate({"id": "h2", "statement": "x", "status": status})

    Hypothesis.model_validate(
        {"id": "h2", "statement": "x", "status": status, "evidence": [TRACE_EVIDENCE]}
    )


def test_hypothesis_ids_are_short() -> None:
    with pytest.raises(ValidationError, match="id"):
        Hypothesis(id="hypothesis-1", statement="x")
