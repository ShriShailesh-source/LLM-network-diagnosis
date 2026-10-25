import pytest

from Validation.models import ValidationInput
from Validation.validator import validate, validate_payload


def diagnosis(**overrides):
    values = {
        "event_id": "EVT001",
        "device_id": "R1",
        "target_interface": "GigabitEthernet0/1",
        "detected_fault": "interface_down",
        "candidate_command": "no shutdown",
        "confidence_score": 0.95,
    }
    values.update(overrides)
    return ValidationInput(**values)


def test_valid_device_and_interface():
    result = validate(diagnosis())
    assert result == {"valid": True, "errors": []}


def test_invalid_device_is_rejected():
    result = validate(diagnosis(device_id="R99"))
    assert result["valid"] is False
    assert any("Unknown device" in error for error in result["errors"])


def test_invalid_interface_is_rejected():
    result = validate(diagnosis(target_interface="GigabitEthernet9/9"))
    assert result["valid"] is False
    assert any("Unknown interface" in error for error in result["errors"])


def test_valid_command():
    assert validate(diagnosis(candidate_command="no shutdown"))["valid"] is True


def test_invalid_or_unsupported_command_is_rejected():
    result = validate(diagnosis(candidate_command="reload"))
    assert result["valid"] is False
    assert any("Unsupported" in error for error in result["errors"])


def test_malformed_ip_command_is_rejected():
    result = validate(diagnosis(
        detected_fault="missing_ip_address",
        candidate_command="ip address 999.1.1.1 255.255.255.0",
    ))
    assert result["valid"] is False


def test_command_appropriate_to_network_state():
    # The built-in R1/Gi0/1 simulation is administratively down.
    assert validate(diagnosis())["valid"] is True


def test_command_inappropriate_to_network_state_is_rejected():
    result = validate(diagnosis(interface_state="up"))
    assert result["valid"] is False
    assert any("already up" in error for error in result["errors"])


def test_correct_fault_fix_pair():
    result = validate(diagnosis(
        detected_fault="missing_ip_address",
        candidate_command="ip address 192.0.2.10 255.255.255.0",
        current_config={},
    ))
    assert result["valid"] is True


def test_incorrect_fault_fix_pair_is_rejected():
    result = validate(diagnosis(
        detected_fault="interface_down",
        candidate_command="ip address 192.0.2.10 255.255.255.0",
    ))
    assert result["valid"] is False
    assert any("does not address detected fault" in error for error in result["errors"])


@pytest.mark.parametrize("score", [-0.01, 1.01, float("nan"), float("inf"), True, "0.8"])
def test_invalid_confidence_score_is_rejected(score):
    result = validate(diagnosis(confidence_score=score))
    assert result["valid"] is False
    assert any("confidence_score" in error for error in result["errors"])


def test_overall_valid_llm_diagnosis_payload():
    result = validate_payload({
        "event_id": "EVT100",
        "device_id": "R1",
        "target_interface": "GigabitEthernet0/1",
        "detected_fault": "interface_down",
        "candidate_command": "no shutdown",
        "confidence_score": 0.92,
    })
    assert result == {"valid": True, "errors": []}


def test_overall_rejected_llm_diagnosis_payload():
    result = validate_payload({
        "event_id": "EVT101",
        "device_id": "R1",
        "target_interface": "GigabitEthernet9/9",
        "detected_fault": "interface_down",
        "candidate_command": "no shutdown",
        "confidence_score": 0.92,
    })
    assert result["valid"] is False
    assert any("Unknown interface" in error for error in result["errors"])


def test_payload_requires_all_llm_fields():
    result = validate_payload({"event_id": "EVT102"})
    assert result["valid"] is False
    assert any("Missing diagnosis field" in error for error in result["errors"])


def test_ip_command_requires_a_changed_address():
    result = validate(diagnosis(
        detected_fault="incorrect_ip_address",
        candidate_command="ip address 192.0.2.10 255.255.255.0",
        current_config={"ip_address": "192.0.2.10 255.255.255.0"},
    ))
    assert result["valid"] is False
    assert any("already has" in error for error in result["errors"])
