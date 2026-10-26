from ai_engine import DiagnosisResult
from log_preprocessor import ParsedLogEvent
from Validation.decision import evaluate_decision
from Validation.evidence import check_evidence
from Validation.expected_state import predict_expected_state, verify_expected_state
from Validation.risk import classify_risk


def event(
    *,
    device: str = "R1",
    interface: str = "GigabitEthernet0/1",
    state: str = "admin_down",
    fault: str = "interface_down",
) -> ParsedLogEvent:
    return ParsedLogEvent(
        event_id="EVT-1",
        device_id=device,
        timestamp=None,
        target_interface=interface,
        detected_fault=fault,
        raw_message="fixture evidence",
        interface_state=state,
        fault_type=fault,
    )


def diagnosis(**overrides: str | float) -> DiagnosisResult:
    values = {
        "event_id": "EVT-1",
        "device_id": "R1",
        "target_interface": "GigabitEthernet0/1",
        "detected_fault": "interface_down",
        "candidate_command": "no shutdown",
        "confidence_score": 0.9,
    }
    values.update(overrides)
    return DiagnosisResult(**values)


def test_supported_interface_fault_is_accepted():
    result = evaluate_decision(diagnosis(), event())
    assert result.final_decision == "ACCEPT"
    assert result.evidence.supported is True
    assert result.risk.risk_level == "LOW"


def test_up_interface_contradiction_produces_no_action():
    result = evaluate_decision(diagnosis(), event(state="up"))
    assert result.final_decision == "NO_ACTION"
    assert result.evidence.supported is False


def test_wrong_device_is_not_redirected_to_another_device():
    reported = event(device="R1", state="up")
    actual = event(device="R2", state="admin_down")
    result = evaluate_decision(
        diagnosis(), reported, all_evidence=[reported, actual]
    )
    assert result.final_decision == "NO_ACTION"
    assert any("wrong device" in reason.lower() for reason in result.evidence.reasons)


def test_wrong_command_is_rejected_by_existing_validator():
    result = evaluate_decision(
        diagnosis(candidate_command="ip address 10.0.99.1 255.255.255.0"),
        event(),
    )
    assert result.final_decision == "REJECT"
    assert result.validation_result["valid"] is False


def test_reload_is_critical_and_rejected_before_validation():
    result = evaluate_decision(diagnosis(candidate_command="reload"), event())
    assert classify_risk("reload").risk_level == "CRITICAL"
    assert result.final_decision == "REJECT"


def test_expected_state_success_and_failure():
    expected = predict_expected_state("admin_down", "no shutdown")
    assert expected.expected_state == "up/up"
    assert verify_expected_state(expected, "up/up")
    assert not verify_expected_state(expected, "admin_down/down")

    success = evaluate_decision(diagnosis(), event(), observed_state="up/up")
    failure = evaluate_decision(
        diagnosis(), event(), observed_state="admin_down/down"
    )
    assert success.final_decision == "REMEDIATION_VERIFIED"
    assert failure.final_decision == "ESCALATE"


def test_evidence_checker_reports_fault_mismatch():
    result = check_evidence(
        diagnosis(detected_fault="ospf_neighbor_down"),
        event(),
    )
    assert result.supported is False
    assert result.evidence_score < 1.0
