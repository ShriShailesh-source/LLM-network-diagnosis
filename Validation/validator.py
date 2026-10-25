"""Public entry points for validating LLM-generated diagnoses."""
from .models import ValidationInput
from .rules import validate_rules


def validate(data: ValidationInput) -> dict:
    errors = validate_rules(data)
    return {"valid": not errors, "errors": errors}


def validate_payload(payload: dict) -> dict:
    """Validate the six-field diagnosis output, with optional state snapshot."""
    try:
        data = ValidationInput.from_payload(payload)
    except (TypeError, ValueError) as exc:
        return {"valid": False, "errors": [str(exc)]}
    return validate(data)
