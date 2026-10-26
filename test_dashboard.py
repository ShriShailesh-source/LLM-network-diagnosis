import json
from http.client import HTTPConnection
from threading import Thread
from http.server import HTTPServer

from dashboard import DashboardHandler, _decision_response, app


def test_dashboard_health_and_validation_endpoint():
    server = HTTPServer(("127.0.0.1", 0), DashboardHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection(*server.server_address)
        connection.request("GET", "/health")
        assert json.loads(connection.getresponse().read()) == {"status": "ok"}
        payload = {
            "event_id": "DASH-1",
            "device_id": "R1",
            "target_interface": "GigabitEthernet0/1",
            "detected_fault": "interface_down",
            "candidate_command": "no shutdown",
            "confidence_score": 0.9,
            "interface_state": "admin_down",
        }
        connection.request(
            "POST", "/api/validate",
            body=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert json.loads(connection.getresponse().read())["valid"] is True
        connection.close()
    finally:
        server.shutdown()
        server.server_close()


def test_dashboard_exposes_an_asgi_application():
    assert callable(app)


def test_dashboard_exposes_evidence_gated_decision_details():
    response = _decision_response({
        "event_id": "DASH-2",
        "device_id": "R1",
        "target_interface": "GigabitEthernet0/1",
        "detected_fault": "interface_down",
        "candidate_command": "no shutdown",
        "confidence_score": 0.9,
        "evidence": {
            "device_id": "R1",
            "target_interface": "GigabitEthernet0/1",
            "detected_fault": "interface_down",
            "fault_type": "interface_down",
            "interface_state": "admin_down",
            "raw_message": "fixture",
        },
    })
    assert response["final_decision"] == "ACCEPT"
    assert response["evidence_supported"] is True
    assert response["risk_level"] == "LOW"
    assert response["expected_state"]["expected_state"] == "up/up"
