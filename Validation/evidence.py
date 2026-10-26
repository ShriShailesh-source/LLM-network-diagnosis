"""Deterministic consistency checks between evidence and an LLM diagnosis."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable

from ai_engine import DiagnosisResult
from log_preprocessor import ParsedLogEvent


@dataclass(frozen=True)
class EvidenceCheck:
    """Outcome of checking a diagnosis against structured network evidence."""

    supported: bool
    evidence_score: float
    reasons: list[str]
    status: str = "SUPPORTED"


def _canonical_fault(value: str) -> str:
    normalized = "_".join(value.strip().lower().replace("-", " ").split())
    if "ospf" in normalized and ("neighbor" in normalized or "adj" in normalized):
        return "ospf_neighbor_down"
    if "incorrect_ip" in normalized or "ip_misconfiguration" in normalized:
        return "incorrect_ip"
    if "interface" in normalized and "down" in normalized:
        return "interface_down"
    return normalized


def check_evidence(
    diagnosis: DiagnosisResult,
    evidence: ParsedLogEvent,
    *,
    all_evidence: Iterable[ParsedLogEvent] | None = None,
) -> EvidenceCheck:
    """Compare diagnosis identity, state, and fault type with evidence.

    ``all_evidence`` may contain events from multiple devices. It is used only
    to explain a likely wrong-device report; it never changes the reported
    target or silently selects a different device for remediation.
    """
    reasons: list[str] = []
    checks = 0
    passed = 0
    if diagnosis.device_id == evidence.device_id:
        passed += 1
        reasons.append("Device identity matches evidence")
    else:
        reasons.append(
            f"Device mismatch: diagnosis targets {diagnosis.device_id}, "
            f"evidence identifies {evidence.device_id}"
        )
    checks += 1

    if diagnosis.target_interface == evidence.target_interface:
        passed += 1
        reasons.append("Target interface matches evidence")
    else:
        reasons.append("Target interface does not match evidence")
    checks += 1

    diagnosis_fault = _canonical_fault(diagnosis.detected_fault)
    evidence_fault = _canonical_fault(evidence.fault_type or evidence.detected_fault)
    if diagnosis_fault == evidence_fault:
        passed += 1
        reasons.append("Fault type matches evidence")
    else:
        reasons.append(
            f"Fault type mismatch: diagnosis={diagnosis_fault}, evidence={evidence_fault}"
        )
    checks += 1

    state = evidence.interface_state
    state_supported = (
        diagnosis_fault != "interface_down"
        or state in {"admin_down", "down"}
    )
    if state_supported:
        passed += 1
        reasons.append(f"Interface state supports {diagnosis_fault}: {state or 'not supplied'}")
    else:
        reasons.append(
            f"Interface state contradicts {diagnosis_fault}: {state or 'not supplied'}"
        )
    checks += 1

    events = list(all_evidence or ())
    wrong_device = any(
        item.device_id != diagnosis.device_id
        and item.target_interface == diagnosis.target_interface
        and item.interface_state in {"admin_down", "down"}
        for item in events
    )
    if wrong_device:
        reasons.append("A matching fault is present on another device; wrong device suspected")

    supported = passed == checks and not wrong_device
    return EvidenceCheck(
        supported=supported,
        evidence_score=round(passed / checks, 3),
        reasons=reasons,
        status="SUPPORTED" if supported else "UNSUPPORTED",
    )
