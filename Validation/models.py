from dataclasses import dataclass


@dataclass
class ValidationInput:
    event_id: str
    device_id: str
    target_interface: str
    detected_fault: str
    candidate_command: str
    confidence_score: float