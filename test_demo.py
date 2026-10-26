from io import StringIO

from Validation.validator import validate_payload
from demo import PACKET_TRACER_FIXTURE, run_demo


def test_packet_tracer_fixture_is_parsed_and_valid_scenario_reaches_acceptance():
    output = StringIO()
    results = run_demo(output)
    valid = results[0]

    assert PACKET_TRACER_FIXTURE.is_file()
    assert "administratively down" in valid["event"].raw_message
    assert valid["event"].device_id == "R1"
    assert valid["event"].target_interface == "GigabitEthernet0/1"
    assert valid["event"].interface_state == "admin_down"
    assert valid["diagnosis"].detected_fault == "interface_down"
    assert valid["diagnosis"].candidate_command == "no shutdown"
    assert valid["validation"]["valid"] is True
    assert "Packet Tracer state: admin_down" in output.getvalue()
    assert "Validation: ACCEPTED" in output.getvalue()


def test_invalid_fix_is_rejected_by_validation_module():
    output = StringIO()
    results = run_demo(output)
    invalid = results[1]

    expected = validate_payload(
        invalid["diagnosis"], interface_state=invalid["interface_state"]
    )
    assert expected["valid"] is False
    assert invalid["validation"] == expected
    assert "does not address detected fault" in " ".join(expected["errors"])
    for error in expected["errors"]:
        assert error in output.getvalue()
    assert "Validation: REJECTED" in output.getvalue()
