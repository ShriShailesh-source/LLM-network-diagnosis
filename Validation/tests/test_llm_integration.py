"""Integration coverage for the six-field DiagnosisResult handoff contract.

The diagnosis engine is absent from this branch, so this deterministic fixture
mirrors its Pydantic model_dump() contract without calling a live LLM API.
"""
from dataclasses import asdict, dataclass

import pytest

from Validation.validator import validate_payload


@dataclass(frozen=True)
class DiagnosisResultFixture:
    event_id: str
    device_id: str
    target_interface: str
    detected_fault: str
    candidate_command: str
    confidence_score: float

    def model_dump(self) -> dict:
        """Match the six-field dictionary emitted by ai_engine.DiagnosisResult."""
        return asdict(self)


def diagnosis(**overrides) -> DiagnosisResultFixture:
    values = {
        "event_id": "EVT001",
        "device_id": "R1",
        "target_interface": "GigabitEthernet0/1",
        "detected_fault": "interface_down",
        "candidate_command": "no shutdown",
        "confidence_score": 0.95,
    }
    values.update(overrides)
    return DiagnosisResultFixture(**values)


def test_llm_diagnosis_result_flows_through_validation_adapter():
    result = validate_payload(diagnosis())
    assert result == {"valid": True, "errors": []}


@pytest.mark.parametrize("device_id", ["R9", "nonexistent-device"])
def test_nonexistent_device_is_rejected(device_id):
    result = validate_payload(diagnosis(device_id=device_id))
    assert result["valid"] is False
    assert any("Unknown device" in error for error in result["errors"])


def test_nonexistent_interface_is_rejected():
    result = validate_payload(diagnosis(target_interface="GigabitEthernet9/9"))
    assert result["valid"] is False
    assert any("Unknown interface" in error for error in result["errors"])


def test_unsupported_command_is_rejected():
    result = validate_payload(diagnosis(candidate_command="reload"))
    assert result["valid"] is False
    assert any("Unsupported" in error for error in result["errors"])


def test_command_that_does_not_match_fault_is_rejected():
    result = validate_payload(diagnosis(
        detected_fault="interface_down",
        candidate_command="ip address 192.0.2.10 255.255.255.0",
    ))
    assert result["valid"] is False
    assert any("does not address detected fault" in error for error in result["errors"])


def test_invalid_confidence_score_is_rejected():
    result = validate_payload(diagnosis(confidence_score=1.01))
    assert result["valid"] is False
    assert any("confidence_score" in error for error in result["errors"])


def test_no_shutdown_requires_administratively_down_evidence():
    result = validate_payload(diagnosis(), interface_state="down")
    assert result["valid"] is False
    assert any("administratively down" in error for error in result["errors"])


def test_valid_fix_is_accepted_when_state_evidence_matches():
    result = validate_payload(diagnosis(), interface_state="admin_down")
    assert result == {"valid": True, "errors": []}


def test_valid_payload_has_exact_diagnosis_contract_fields():
    payload = diagnosis().model_dump()
    assert set(payload) == {
        "event_id", "device_id", "target_interface", "detected_fault",
        "candidate_command", "confidence_score",
    }
    assert type(payload["confidence_score"]) is float
