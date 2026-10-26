"""Administrator-facing dashboard with ASGI and standard-library entry points."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

from ai_engine import DiagnosisResult
from log_preprocessor import ParsedLogEvent
from Validation.decision import evaluate_decision
from Validation.validator import validate_payload


HTML = """<!doctype html><title>Network Troubleshooting</title>
<h1>NETWORK TROUBLESHOOTING</h1>
<p>POST JSON to <code>/api/validate</code> to validate an untrusted diagnosis.</p>
<pre id="result">Use the API endpoint with a diagnosis payload.</pre>"""

ASGIMessage = dict[str, object]
ASGISend = Callable[[ASGIMessage], Awaitable[None]]


async def app(
    scope: ASGIMessage,
    receive: Callable[[], Awaitable[ASGIMessage]],
    send: ASGISend,
) -> None:
    """Serve the dashboard as a minimal ASGI application for Uvicorn."""
    if scope.get("type") == "lifespan":
        while True:
            message = await receive()
            message_type = message.get("type")
            if message_type == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message_type == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
        return

    if scope.get("type") != "http":
        return

    method = str(scope.get("method", "GET")).upper()
    path = str(scope.get("path", "/"))
    if method == "GET" and path == "/health":
        await _asgi_json(send, {"status": "ok"})
        return
    if method == "GET" and path == "/":
        await _asgi_response(
            send, 200, HTML.encode("utf-8"), "text/html; charset=utf-8"
        )
        return
    if method == "POST" and path == "/api/validate":
        body = bytearray()
        while True:
            message = await receive()
            body.extend(message.get("body", b""))
            if not message.get("more_body", False):
                break
        try:
            payload = json.loads(bytes(body))
            result = _decision_response(payload)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            await _asgi_json(
                send,
                {"valid": False, "errors": [f"Invalid JSON request: {exc}"]},
                status=400,
            )
            return
        await _asgi_json(send, result)
        return
    await _asgi_response(send, 404, b"Not found\n", "text/plain; charset=utf-8")


async def _asgi_json(
    send: ASGISend, value: dict[str, object], status: int = 200
) -> None:
    await _asgi_response(
        send,
        status,
        json.dumps(value).encode("utf-8"),
        "application/json",
    )


async def _asgi_response(
    send: ASGISend, status: int, body: bytes, content_type: str
) -> None:
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            [b"content-type", content_type.encode("ascii")],
            [b"content-length", str(len(body)).encode("ascii")],
        ],
    })
    await send({"type": "http.response.body", "body": body})


def _decision_response(payload: dict) -> dict:
    """Return evidence-gated decision details when structured evidence is supplied."""
    evidence_payload = payload.get("evidence")
    if not isinstance(evidence_payload, dict):
        return validate_payload(
            payload,
            interface_state=payload.get("interface_state"),
            current_config=payload.get("current_config"),
        )
    diagnosis = DiagnosisResult.model_validate({
        key: payload[key]
        for key in (
            "event_id", "device_id", "target_interface", "detected_fault",
            "candidate_command", "confidence_score",
        )
        if key in payload
    })
    evidence = ParsedLogEvent(
        event_id=str(evidence_payload.get("event_id", "evidence")),
        device_id=evidence_payload.get("device_id"),
        timestamp=evidence_payload.get("timestamp"),
        target_interface=str(evidence_payload.get("target_interface", "")),
        detected_fault=str(evidence_payload.get("detected_fault", "")),
        raw_message=str(evidence_payload.get("raw_message", "")),
        interface_state=evidence_payload.get("interface_state"),
        fault_type=str(evidence_payload.get("fault_type", "interface_down")),
        protocol=evidence_payload.get("protocol"),
        neighbor_id=evidence_payload.get("neighbor_id"),
    )
    result = evaluate_decision(
        diagnosis,
        evidence,
        observed_state=payload.get("observed_state"),
        current_config=payload.get("current_config"),
    )
    return {
        "diagnosis": diagnosis.model_dump(),
        "evidence_supported": result.evidence.supported,
        "evidence_score": result.evidence.evidence_score,
        "evidence_reasons": result.evidence.reasons,
        "risk_level": result.risk.risk_level,
        "blast_radius": result.risk.blast_radius,
        "reversible": result.risk.reversible,
        "validation_result": result.validation_result,
        "expected_state": result.expected_state.__dict__,
        "final_decision": result.final_decision,
        "reason": result.reason,
    }


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if urlparse(self.path).path == "/health":
            self._json({"status": "ok"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode("utf-8"))

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/validate":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            result = _decision_response(payload)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._json({"valid": False, "errors": [f"Invalid JSON request: {exc}"]}, 400)
            return
        self._json(result)

    def _json(self, value: dict, status: int = 200) -> None:
        body = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> None:
    server = HTTPServer(("127.0.0.1", 8000), DashboardHandler)
    print("Dashboard running at http://127.0.0.1:8000")
    server.serve_forever()


if __name__ == "__main__":
    main()
