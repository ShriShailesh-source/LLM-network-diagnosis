"""Evidence-gated decision orchestration for diagnosis remediation."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable

from ai_engine import DiagnosisResult
from log_preprocessor import ParsedLogEvent

from .evidence import EvidenceCheck, check_evidence
from .expected_state import ExpectedState, predict_expected_state, verify_expected_state
from .risk import RiskAssessment, classify_risk
from .validator import validate_payload


@dataclass(frozen=True)
class DecisionResult:
    """Complete evidence, risk, validation, and expected-state decision."""

    final_decision: str
    evidence: EvidenceCheck
    risk: RiskAssessment
    validation_result: dict
    expected_state: ExpectedState
    reason: str


def evaluate_decision(
    diagnosis: DiagnosisResult,
    evidence: ParsedLogEvent,
    *,
    all_evidence: Iterable[ParsedLogEvent] | None = None,
    observed_state: str | None = None,
    current_config: dict | None = None,
) -> DecisionResult:
    """Apply the ordered evidence-gated remediation policy."""
    evidence_result = check_evidence(diagnosis, evidence, all_evidence=all_evidence)
    risk_result = classify_risk(diagnosis.candidate_command)
    expected = predict_expected_state(
        evidence.interface_state or "unknown",
        diagnosis.candidate_command,
    )
    if not evidence_result.supported:
        return DecisionResult(
            "NO_ACTION", evidence_result, risk_result,
            {"valid": False, "errors": ["Diagnosis is not supported by network evidence"]},
            expected, "Diagnosis is not supported by network evidence",
        )
    if risk_result.risk_level in {"CRITICAL", "HIGH", "UNKNOWN"}:
        return DecisionResult(
            "REJECT", evidence_result, risk_result,
            {"valid": False, "errors": [risk_result.reason]},
            expected, f"Risk policy does not permit automatic remediation: {risk_result.risk_level}",
        )
    validation = validate_payload(
        diagnosis,
        interface_state=evidence.interface_state,
        current_config=current_config,
    )
    if not validation["valid"]:
        return DecisionResult(
            "REJECT", evidence_result, risk_result, validation,
            expected, "Independent configuration validation rejected the candidate",
        )
    if observed_state is not None:
        if verify_expected_state(expected, observed_state):
            return DecisionResult(
                "REMEDIATION_VERIFIED", evidence_result, risk_result,
                validation, expected, "Observed post-fix state matches expected state",
            )
        return DecisionResult(
            "ESCALATE", evidence_result, risk_result, validation,
            expected, "Observed post-fix state does not match expected state",
        )
    return DecisionResult(
        "ACCEPT", evidence_result, risk_result, validation,
        expected, "Evidence, risk, and independent validation passed",
    )
