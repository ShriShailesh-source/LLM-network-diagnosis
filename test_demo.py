from io import StringIO

from Validation.validator import validate_payload
from demo import PACKET_TRACER_FIXTURE, RECOVERY_RESULT, run_demo


def test_demo_presents_evidence_through_recovery_verification():
    output = StringIO()
    results = run_demo(output)
    valid = results[0]
    report = output.getvalue()

    assert PACKET_TRACER_FIXTURE.is_file()
    assert "administratively down" in valid["event"].raw_message
    assert valid["event"].device_id == "R1"
    assert valid["event"].target_interface == "GigabitEthernet0/1"
    assert valid["event"].interface_state == "admin_down"
    assert valid["diagnosis"].detected_fault == "interface_down"
    assert valid["diagnosis"].candidate_command == "no shutdown"
    assert valid["validation"]["valid"] is True
    for stage in (
        "1. Packet Tracer evidence",
        "2. Parsed network event",
        "3. LLM diagnosis",
        "4. Candidate fix",
        "5. Validation checks",
        "6. Validation result: ACCEPTED",
        "7. Recovery verification",
    ):
        assert stage in report
    assert "Router0 GigabitEthernet0/1: up/up" in report
    assert "Client: deterministic injected test/demo client (no API call)" in report
    for address in RECOVERY_RESULT["pings"]:
        assert address in report


def test_invalid_fix_is_rejected_by_validation_module_and_not_recovered():
    output = StringIO()
    results = run_demo(output)
    invalid = results[1]
    report = output.getvalue()

    expected = validate_payload(
        invalid["diagnosis"], interface_state=invalid["interface_state"]
    )
    assert expected["valid"] is False
    assert invalid["validation"] == expected
    assert "does not address detected fault" in " ".join(expected["errors"])
    for error in expected["errors"]:
        assert error in report
    assert "6. Validation result: REJECTED" in report
    assert "Not attempted: validation rejected the candidate command." in report
