from io import StringIO

from Validation.validator import validate_payload
from demo import run_demo


def test_valid_demo_scenario_reaches_accepted():
    output = StringIO()
    results = run_demo(output)

    assert results[0]["validation"]["valid"] is True
    assert "Event: EVT001" in output.getvalue()
    assert "Simulated state: admin_down" in output.getvalue()
    assert "Validation: ACCEPTED" in output.getvalue()


def test_invalid_demo_scenario_reaches_rejected():
    output = StringIO()
    results = run_demo(output)

    assert results[1]["validation"]["valid"] is False
    assert "Validation: REJECTED" in output.getvalue()


def test_demo_displays_errors_returned_by_validation_module():
    output = StringIO()
    results = run_demo(output)
    invalid = results[1]
    expected = validate_payload(
        invalid["diagnosis"],
        interface_state=invalid["interface_state"],
    )

    assert expected["valid"] is False
    assert invalid["validation"] == expected
    for error in expected["errors"]:
        assert error in output.getvalue()
