from .models import ValidationInput
from .rules import validate_rules


def validate(data: ValidationInput) -> dict:
    errors = validate_rules(data)

    return {
        "valid": len(errors) == 0,
        "errors": errors
    }