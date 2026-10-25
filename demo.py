"""Run a deterministic network-log → diagnosis → validation demonstration."""
from __future__ import annotations

import sys
from dataclasses import replace
from types import SimpleNamespace
from typing import Any, TextIO

from ai_engine import DiagnosisResult, diagnose_event
from log_preprocessor import parse_logs
from Validation.validator import validate_payload


SAMPLE_LOG = "%LINK-3-UPDOWN: Interface GigabitEthernet0/1 is down"
SIMULATED_DEVICE = "R1"
SIMULATED_INTERFACE_STATE = "admin_down"


class _DeterministicClient:
    """Provide fixed structured diagnoses through ai_engine's client seam."""

    def __init__(self, result: DiagnosisResult) -> None:
        self.models = SimpleNamespace(
            generate_content=lambda **_kwargs: SimpleNamespace(
                parsed=result,
                text=result.model_dump_json(),
            )
        )


def _run_scenario(
    *,
    event_id: str,
    detected_fault: str,
    candidate_command: str,
    confidence_score: float,
) -> dict[str, Any]:
    events = parse_logs(SAMPLE_LOG, device_id=SIMULATED_DEVICE)
    if not events:
        raise RuntimeError("The sample network log produced no parsed event")
    event = replace(events[0], event_id=event_id)
    proposed_diagnosis = DiagnosisResult(
        event_id=event.event_id,
        device_id=event.device_id or "",
        target_interface=event.target_interface,
        detected_fault=detected_fault,
        candidate_command=candidate_command,
        confidence_score=confidence_score,
    )

    diagnosis = diagnose_event(event, client=_DeterministicClient(proposed_diagnosis))
    validation = validate_payload(
        diagnosis,
        interface_state=SIMULATED_INTERFACE_STATE,
    )
    return {
        "event": event,
        "diagnosis": diagnosis,
        "interface_state": SIMULATED_INTERFACE_STATE,
        "validation": validation,
    }


def run_demo(output: TextIO | None = None) -> list[dict[str, Any]]:
    """Print the two demo scenarios and return their real pipeline results."""
    if output is None:
        output = sys.stdout

    scenarios = [
        {
            "event_id": "EVT001",
            "detected_fault": "interface_down",
            "candidate_command": "no shutdown",
            "confidence_score": 0.95,
        },
        {
            "event_id": "EVT002",
            "detected_fault": "interface_down",
            "candidate_command": "ip address 192.0.2.10 255.255.255.0",
            "confidence_score": 0.91,
        },
    ]

    print("=== NETWORK TROUBLESHOOTING DEMO ===", file=output)
    results = []
    for number, scenario in enumerate(scenarios, start=1):
        result = _run_scenario(**scenario)
        diagnosis = result["diagnosis"]
        validation = result["validation"]
        label = "Valid diagnosis" if number == 1 else "Invalid diagnosis"
        print(f"\n--- Scenario {number}: {label} ---", file=output)
        print(f"Event: {diagnosis.event_id}", file=output)
        print(f"Device: {diagnosis.device_id}", file=output)
        print(f"Interface: {diagnosis.target_interface}", file=output)
        print(f"Detected fault: {diagnosis.detected_fault}", file=output)
        print(f"Candidate command: {diagnosis.candidate_command}", file=output)
        print(f"Confidence: {diagnosis.confidence_score:.2f}", file=output)
        print("Simulated state: " + result["interface_state"], file=output)

        if validation["valid"]:
            print("\nValidation: ACCEPTED", file=output)
        else:
            print("\nValidation: REJECTED", file=output)
            print("\nReason:", file=output)
            for error in validation["errors"]:
                print(f"- {error}", file=output)
        results.append(result)

    return results


if __name__ == "__main__":
    run_demo()
