"""Small administrator-facing HTTP dashboard using only the standard library."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from ai_engine import DiagnosisResult
from Validation.validator import validate_payload


HTML = """<!doctype html><title>Network Troubleshooting</title>
<h1>NETWORK TROUBLESHOOTING</h1>
<p>POST JSON to <code>/api/validate</code> to validate an untrusted diagnosis.</p>
<pre id="result">Use the API endpoint with a diagnosis payload.</pre>"""


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
            result = validate_payload(
                payload,
                interface_state=payload.get("interface_state"),
                current_config=payload.get("current_config"),
            )
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
