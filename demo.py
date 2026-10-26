"""Present the Packet Tracer evidence through diagnosis and validation."""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TextIO

from ai_engine import DiagnosisResult, diagnose_event
from log_preprocessor import parse_logs
from Validation.validator import validate_payload


PACKET_TRACER_FIXTURE = Path(__file__).parent / "logs" / "packet_tracer_router0.txt"
# Router0 in the Packet Tracer transcript maps to the existing R1 inventory.
SIMULATED_DEVICE = "R1"
VALIDATION_CHECKS = (
    "Required diagnosis fields and confidence",
    "Device and interface existence",
    "Command syntax and supported command",
    "Current network-state safety",
    "Fault-to-fix correspondence",
)
RECOVERY_RESULT = {
    "interface_status": "up/up",
    "pings": (
        "192.168.1.1",
        "10.0.0.2",
        "192.168.2.1",
        "192.168.2.10",
    ),
}


class _DeterministicClient:
    """Supply a fixed structured result through ai_engine's client seam."""

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
    raw_evidence = PACKET_TRACER_FIXTURE.read_text(encoding="utf-8-sig")
    events = parse_logs(raw_evidence, device_id=SIMULATED_DEVICE)
    event = next(
        (item for item in events if item.target_interface == "GigabitEthernet0/1"),
        None,
    )
    if event is None:
        raise RuntimeError("Packet Tracer fixture has no G0/1 down event")
    if event.interface_state is None:
        raise RuntimeError("Packet Tracer fixture has no G0/1 state evidence")
    event = replace(event, event_id=event_id)
    proposed_diagnosis = DiagnosisResult(
        event_id=event.event_id,
        device_id=event.device_id or "",
        target_interface=event.target_interface,
        detected_fault=detected_fault,
        candidate_command=candidate_command,
        confidence_score=confidence_score,
    )

    diagnosis = diagnose_event(event, client=_DeterministicClient(proposed_diagnosis))
    validation = validate_payload(diagnosis, interface_state=event.interface_state)
    return {
        "event": event,
        "diagnosis": diagnosis,
        "interface_state": event.interface_state,
        "validation": validation,
    }


def _print_scenario(result: dict[str, Any], *, output: TextIO, valid_case: bool) -> None:
    event = result["event"]
    diagnosis = result["diagnosis"]
    validation = result["validation"]
    label = "Valid diagnosis" if valid_case else "Invalid diagnosis"

    print(f"\n--- {label} ---", file=output)
    print("1. Packet Tracer evidence", file=output)
    print("   Router0#show ip interface brief", file=output)
    print(f"   {event.raw_message}", file=output)

    print("2. Parsed network event", file=output)
    print(f"   Event ID: {event.event_id}", file=output)
    print(f"   Device: {event.device_id} (Packet Tracer Router0)", file=output)
    print(f"   Interface: {event.target_interface}", file=output)
    print(f"   Parsed fault: {event.detected_fault}", file=output)
    print(f"   Observed interface state: {event.interface_state}", file=output)

    print("3. LLM diagnosis", file=output)
    print("   Diagnosis interface: ai_engine.diagnose_event", file=output)
    print("   Client: deterministic injected test/demo client (no API call)", file=output)
    print(f"   Detected fault: {diagnosis.detected_fault}", file=output)
    print(f"   Confidence: {diagnosis.confidence_score:.2f}", file=output)

    print("4. Candidate fix", file=output)
    print(f"   {diagnosis.candidate_command}", file=output)

    print("5. Validation checks", file=output)
    for check in VALIDATION_CHECKS:
        print(f"   - {check}", file=output)

    if validation["valid"]:
        print("6. Validation result: ACCEPTED", file=output)
        print("7. Recovery verification", file=output)
        print("   Packet Tracer follow-up reported by user:", file=output)
        print(f"   Router0 GigabitEthernet0/1: {RECOVERY_RESULT['interface_status']}", file=output)
        print("   PC0 ping successful to:", file=output)
        for address in RECOVERY_RESULT["pings"]:
            print(f"   - {address}", file=output)
    else:
        print("6. Validation result: REJECTED", file=output)
        print("   Validation errors:", file=output)
        for error in validation["errors"]:
            print(f"   - {error}", file=output)
        print("7. Recovery verification", file=output)
        print("   Not attempted: validation rejected the candidate command.", file=output)


def run_demo(output: TextIO | None = None) -> list[dict[str, Any]]:
    """Print accepted and rejected pipeline scenarios and return their results."""
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
    for index, scenario in enumerate(scenarios):
        result = _run_scenario(**scenario)
        _print_scenario(result, output=output, valid_case=index == 0)
        results.append(result)
    return results


if __name__ == "__main__":
    run_demo()
