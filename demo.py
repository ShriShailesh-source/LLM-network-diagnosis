"""Presentation demo for the evidence-gated remediation architecture."""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TextIO

from ai_engine import DiagnosisResult, diagnose_event
from log_preprocessor import ParsedLogEvent, parse_logs
from Validation.decision import DecisionResult, evaluate_decision
from Validation.validator import validate_payload


PACKET_TRACER_FIXTURE = Path(__file__).parent / "logs" / "packet_tracer_router0.txt"
SIMULATED_DEVICE = "R1"
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


def _packet_tracer_event(event_id: str) -> ParsedLogEvent:
    raw_evidence = PACKET_TRACER_FIXTURE.read_text(encoding="utf-8-sig")
    events = parse_logs(raw_evidence, device_id=SIMULATED_DEVICE)
    event = next(
        (item for item in events if item.target_interface == "GigabitEthernet0/1"),
        None,
    )
    if event is None or event.interface_state is None:
        raise RuntimeError("Packet Tracer fixture has no G0/1 state evidence")
    return replace(event, event_id=event_id)


def _state_event(
    *,
    event_id: str,
    device_id: str,
    interface_state: str,
    fault_type: str = "interface_down",
) -> ParsedLogEvent:
    """Build deterministic state evidence for non-Packet-Tracer scenarios."""
    return ParsedLogEvent(
        event_id=event_id,
        device_id=device_id,
        timestamp=None,
        target_interface="GigabitEthernet0/1",
        detected_fault=fault_type,
        raw_message=f"{device_id} GigabitEthernet0/1 state fixture: {interface_state}",
        interface_state=interface_state,
        fault_type=fault_type,
    )


def _run_scenario(
    *,
    event: ParsedLogEvent,
    detected_fault: str,
    candidate_command: str,
    confidence_score: float,
    all_evidence: list[ParsedLogEvent] | None = None,
) -> dict[str, Any]:
    proposed = DiagnosisResult(
        event_id=event.event_id,
        device_id=event.device_id or "",
        target_interface=event.target_interface,
        detected_fault=detected_fault,
        candidate_command=candidate_command,
        confidence_score=confidence_score,
    )
    diagnosis = diagnose_event(event, client=_DeterministicClient(proposed))
    decision = evaluate_decision(
        diagnosis,
        event,
        all_evidence=all_evidence,
    )
    # Keep the original public demo result shape for existing callers/tests.
    validation = validate_payload(
        diagnosis,
        interface_state=event.interface_state,
    )
    return {
        "event": event,
        "diagnosis": diagnosis,
        "interface_state": event.interface_state,
        "validation": validation,
        "decision": decision,
    }


def _print_scenario(
    result: dict[str, Any],
    *,
    output: TextIO,
    title: str,
    packet_tracer: bool = False,
) -> None:
    event = result["event"]
    diagnosis = result["diagnosis"]
    decision: DecisionResult = result["decision"]
    evidence = decision.evidence
    risk = decision.risk
    expected = decision.expected_state
    legacy_validation = result["validation"]

    print(f"\n--- {title} ---", file=output)
    if packet_tracer:
        print("1. Packet Tracer evidence", file=output)
    print("2. Parsed network event", file=output)
    print("\n=== NETWORK EVIDENCE ===", file=output)
    if packet_tracer:
        print("Source: Packet Tracer fixture (simulated evidence)", file=output)
        print("Router0#show ip interface brief", file=output)
    print(f"Device: {event.device_id}", file=output)
    print(f"Interface: {event.target_interface}", file=output)
    print(f"Observed state: {event.interface_state or 'not supplied'}", file=output)
    print(f"Raw evidence: {event.raw_message}", file=output)

    print("\n=== PARSED EVENT ===", file=output)
    print(f"Fault type: {event.fault_type}", file=output)
    print(f"Event ID: {event.event_id}", file=output)

    print("\n3. LLM diagnosis", file=output)
    print("\n=== LLM DIAGNOSIS ===", file=output)
    print(
        "Client: deterministic injected test/demo client (no API call)",
        file=output,
    )
    print(f"Detected fault: {diagnosis.detected_fault}", file=output)
    print(f"Candidate command: {diagnosis.candidate_command or 'NONE'}", file=output)
    print(f"Confidence: {diagnosis.confidence_score:.2f}", file=output)
    print(f"4. Candidate fix: {diagnosis.candidate_command or 'NONE'}", file=output)

    print("\n=== EVIDENCE CONSISTENCY ===", file=output)
    print(f"Supported: {'YES' if evidence.supported else 'NO'}", file=output)
    print(f"Evidence score: {evidence.evidence_score:.3f}", file=output)
    print("Reasons:", file=output)
    for reason in evidence.reasons:
        print(f"- {reason}", file=output)

    print("\n=== RISK ASSESSMENT ===", file=output)
    print(f"Risk level: {risk.risk_level}", file=output)
    print(f"Blast radius: {risk.blast_radius}", file=output)
    print(f"Reversible: {'YES' if risk.reversible else 'NO'}", file=output)
    print(f"Reason: {risk.reason}", file=output)

    print("\n=== CONFIGURATION VALIDATION ===", file=output)
    print("5. Validation checks", file=output)
    print(f"Result: {'ACCEPTED' if decision.validation_result['valid'] else 'REJECTED'}", file=output)
    for error in decision.validation_result["errors"]:
        print(f"- {error}", file=output)
    if legacy_validation != decision.validation_result:
        print("Independent validator result before decision gating:", file=output)
        for error in legacy_validation["errors"]:
            print(f"- {error}", file=output)

    print("\n=== EXPECTED STATE ===", file=output)
    current_state = event.interface_state or "not supplied"
    print(f"Current state: {current_state}/down" if current_state == "admin_down" else f"Current state: {current_state}", file=output)
    print(f"Candidate command: {diagnosis.candidate_command or 'NONE'}", file=output)
    print(f"Expected state: {expected.expected_state or 'not deterministically mapped'}", file=output)

    print("\n=== FINAL DECISION ===", file=output)
    print(
        f"6. Validation result: "
        f"{'ACCEPTED' if decision.final_decision == 'ACCEPT' else 'REJECTED'}",
        file=output,
    )
    print(decision.final_decision, file=output)
    print(f"Reason: {decision.reason}", file=output)

    if packet_tracer and decision.final_decision == "ACCEPT":
        print("7. Recovery verification", file=output)
        print("\n=== RECOVERY VERIFICATION ===", file=output)
        print(f"Router0 GigabitEthernet0/1: {RECOVERY_RESULT['interface_status']}", file=output)
        print("PC0 ping successful to:", file=output)
        for address in RECOVERY_RESULT["pings"]:
            print(f"- {address}", file=output)
    elif decision.final_decision != "ACCEPT":
        print("Not attempted: validation rejected the candidate command.", file=output)


def run_demo(output: TextIO | None = None) -> list[dict[str, Any]]:
    """Print four evidence-gated scenarios using no live API calls."""
    if output is None:
        output = sys.stdout

    supported_event = _packet_tracer_event("EVT001")
    false_fault_event = _state_event(
        event_id="EVT002", device_id="R1", interface_state="up"
    )
    wrong_device_report = _state_event(
        event_id="EVT003", device_id="R1", interface_state="up"
    )
    actual_other_device = _state_event(
        event_id="EVT004", device_id="R2", interface_state="admin_down"
    )
    dangerous_event = _packet_tracer_event("EVT005")

    scenarios = [
        _run_scenario(
            event=supported_event,
            detected_fault="interface_down",
            candidate_command="no shutdown",
            confidence_score=0.95,
        ),
        _run_scenario(
            event=false_fault_event,
            detected_fault="interface_down",
            # This is untrusted model output and is blocked before remediation.
            candidate_command="ip address 192.0.2.10 255.255.255.0",
            confidence_score=0.91,
        ),
        _run_scenario(
            event=wrong_device_report,
            detected_fault="interface_down",
            candidate_command="no shutdown",
            confidence_score=0.90,
            all_evidence=[wrong_device_report, actual_other_device],
        ),
        _run_scenario(
            event=dangerous_event,
            detected_fault="interface_down",
            candidate_command="reload",
            confidence_score=0.90,
        ),
    ]

    print("=== NETWORK TROUBLESHOOTING DEMO ===", file=output)
    _print_scenario(
        scenarios[0], output=output, title="Scenario 1: Supported Fault", packet_tracer=True
    )
    _print_scenario(
        scenarios[1], output=output, title="Scenario 2: False Fault"
    )
    _print_scenario(
        scenarios[2], output=output, title="Scenario 3: Wrong Device"
    )
    _print_scenario(
        scenarios[3], output=output, title="Scenario 4: Dangerous Remediation"
    )
    return scenarios


if __name__ == "__main__":
    run_demo()
