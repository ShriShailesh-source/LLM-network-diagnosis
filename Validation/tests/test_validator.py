from Validation.models import ValidationInput
from Validation.validator import validate


def test_valid_input():
    data = ValidationInput(
        event_id="EVT001",
        device_id="R1",
        target_interface="GigabitEthernet0/1",
        detected_fault="interface_down",
        candidate_command="no shutdown",
        confidence_score=0.95
    )

    result = validate(data)

    assert result["valid"] is True
    assert result["errors"] == []


def test_invalid_confidence():
    data = ValidationInput(
        event_id="EVT002",
        device_id="R2",
        target_interface="GigabitEthernet0/2",
        detected_fault="interface_down",
        candidate_command="no shutdown",
        confidence_score=1.5
    )

    result = validate(data)

    assert result["valid"] is False