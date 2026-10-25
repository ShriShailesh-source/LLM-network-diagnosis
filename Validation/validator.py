"""Public entry points for validating LLM-generated diagnoses."""
from collections.abc import Mapping
from typing import Any

from .models import ValidationInput
from .rules import validate_rules


def validate(data: ValidationInput) -> dict:
    errors = validate_rules(data)
    return {"valid": not errors, "errors": errors}


def validate_payload(
    payload: Any,
    *,
    interface_state: str | None = None,
    current_config: dict | None = None,
) -> dict:
    """Validate DiagnosisResult or its mapping, with simulator state separately."""
    if not isinstance(payload, Mapping):
        model_dump = getattr(payload, "model_dump", None)
        if not callable(model_dump):
            return {
                "valid": False,
                "errors": [
                    "Diagnosis payload must be a mapping or expose model_dump()"
                ],
            }
        try:
            payload = model_dump()
        except (TypeError, ValueError) as exc:
            return {
                "valid": False,
                "errors": [f"Could not read diagnosis payload: {exc}"],
            }
    if not isinstance(payload, Mapping):
        return {"valid": False, "errors": ["model_dump() must return a mapping"]}

    values = dict(payload)
    if interface_state is not None:
        values["interface_state"] = interface_state
    if current_config is not None:
        values["current_config"] = current_config
    try:
        data = ValidationInput.from_payload(values)
    except (TypeError, ValueError) as exc:
        return {"valid": False, "errors": [str(exc)]}
    return validate(data)
