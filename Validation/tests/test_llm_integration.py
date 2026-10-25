"""Integration coverage for the actual DiagnosisResult-to-Validation handoff.

Tests use ai_engine's injected client so production diagnosis code runs without
making a live Gemini API request.
"""
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from ai_engine import DiagnosisResult, diagnose_event
from log_preprocessor import parse_logs
from Validation.validator import validate_payload


def diagnosis(**overrides) -> DiagnosisResult:
    values = {
        "event_id": "EVT001",
        "device_id": "R1",
        "target_interface": "GigabitEthernet0/1",
        "detected_fault": "interface_down",
        "candidate_command": "no shutdown",
        "confidence_score": 0.95,
    }
    values.update(overrides)
    return DiagnosisResult(**values)


def test_actual_diagnose_event_result_flows_into_validation():
    event = parse_logs(
        "%LINK-3-UPDOWN: Interface GigabitEthernet0/1 is down",
        device_id="R1",
    )[0]
    llm_result = DiagnosisResult(
        event_id=event.event_id,
        device_id=event.device_id,
        target_interface=event.target_interface,
        detected_fault="interface_down",
        candidate_command="no shutdown",
        confidence_score=0.95,
    )
    client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **_kwargs: SimpleNamespace(
                parsed=llm_result,
                text=llm_result.model_dump_json(),
            )
        )
    )

    diagnosis_result = diagnose_event(event, client=client)
    assert isinstance(diagnosis_result, DiagnosisResult)
    assert set(diagnosis_result.model_dump()) == {
        "event_id", "device_id", "target_interface", "detected_fault",
        "candidate_command", "confidence_score",
    }
    validation_result = validate_payload(
        diagnosis_result,
        interface_state="admin_down",
    )
    assert validation_result == {"valid": True, "errors": []}


def test_diagnosis_result_object_flows_through_validation_adapter():
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
    # The strict DiagnosisResult rejects this score before validation. This
    # checks the validator's own boundary for untrusted mapping inputs.
    invalid = diagnosis().model_dump()
    invalid["confidence_score"] = 1.01
    result = validate_payload(invalid)
    assert result["valid"] is False
    assert any("confidence_score" in error for error in result["errors"])
    with pytest.raises(ValidationError):
        diagnosis(confidence_score=1.01)


def test_no_shutdown_requires_administratively_down_evidence():
    result = validate_payload(diagnosis(), interface_state="down")
    assert result["valid"] is False
    assert any("administratively down" in error for error in result["errors"])


def test_valid_fix_is_accepted_when_state_evidence_matches():
    result = validate_payload(diagnosis(), interface_state="admin_down")
    assert result == {"valid": True, "errors": []}
