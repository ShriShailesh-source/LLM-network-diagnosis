from .models import ValidationInput


def validate_rules(data: ValidationInput) -> list[str]:
    errors = []

    if not data.event_id:
        errors.append("Missing event_id")

    if not data.device_id:
        errors.append("Missing device_id")

    if not data.target_interface:
        errors.append("Missing target_interface")

    if not data.detected_fault:
        errors.append("Missing detected_fault")

    if not data.candidate_command:
        errors.append("Missing candidate_command")

    if not 0.0 <= data.confidence_score <= 1.0:
        errors.append("confidence_score must be between 0 and 1")

    return errors