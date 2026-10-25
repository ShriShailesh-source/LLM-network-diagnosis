from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationInput:
    event_id: str
    device_id: str
    target_interface: str
    detected_fault: str
    candidate_command: str
    confidence_score: float
    # Optional state snapshot supplied by a simulator or caller.
    interface_state: str | None = None
    current_config: dict[str, Any] | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ValidationInput":
        """Build input from the diagnosis engine's output fields."""
        required = (
            "event_id", "device_id", "target_interface", "detected_fault",
            "candidate_command", "confidence_score",
        )
        missing = [name for name in required if name not in payload]
        if missing:
            raise ValueError("Missing diagnosis field(s): " + ", ".join(missing))
        values = {name: payload[name] for name in required}
        values["interface_state"] = payload.get("interface_state")
        values["current_config"] = payload.get("current_config")
        return cls(**values)
